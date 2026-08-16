"""Turn a mapped upload into rows in the normalized tables."""
from __future__ import annotations

import hashlib
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import DEFAULT_METHODOLOGY
from ..models import (
    AiCall,
    Attendance,
    Bot,
    Client,
    Event,
    GenericDataset,
    GenericRecord,
    RawUpload,
    Registration,
    Sale,
    WebinarDaily,
)
from ..util.normalize import (
    clean_str,
    norm_email,
    norm_phone,
    to_date,
    to_datetime,
    to_float,
    to_int,
)
from .persons import PersonResolver
from .readers import read_table
from .schema import guess_language

BATCH = 1000


def get_or_create_client(db: Session, name: str) -> Client:
    """Look up a client by name, creating it if absent.

    Reserved for the seed/reference-load scripts. API ingest must NOT use this —
    it resolves the client by id from the upload row instead, so a file can never
    land in the wrong org or conjure a new one from a mistyped name.
    """
    name = (name or "").strip()
    if not name:
        raise ValueError("Client name is required")
    client = db.execute(select(Client).where(Client.name == name)).scalar_one_or_none()
    if client is None:
        client = Client(name=name)
        db.add(client)
        db.flush()
    return client


def classify_bot(bot_name: str, params: dict) -> str:
    lowered = (bot_name or "").lower()
    for pattern in params.get("signup_bot_patterns", []):
        if pattern.lower() in lowered:
            return "signup"
    for pattern in params.get("dayof_bot_patterns", []):
        if pattern.lower() in lowered:
            return "day_of"
    return "other"


class BotCache:
    def __init__(self, db: Session, client_id: int, params: dict):
        self.db = db
        self.client_id = client_id
        self.params = params
        self.cache: dict[str, Bot] = {}
        for bot in db.execute(select(Bot).where(Bot.client_id == client_id)).scalars():
            self.cache[bot.name] = bot

    def get(self, name: str | None) -> Bot | None:
        if not name:
            return None
        name = str(name).strip()
        if name in self.cache:
            return self.cache[name]
        bot = Bot(
            client_id=self.client_id,
            name=name,
            role=classify_bot(name, self.params),
            language=guess_language(name),
        )
        self.db.add(bot)
        self.db.flush()
        self.cache[name] = bot
        return bot


def _val(row: dict, mapping: dict, key: str):
    column = mapping.get(key)
    if not column:
        return None
    return row.get(column)


MODEL_BY_TYPE = {
    "registrations": Registration,
    "ai_calls": AiCall,
    "sales": Sale,
    "attendance": Attendance,
    "webinar_daily": WebinarDaily,
    "custom": GenericRecord,
}


def row_hash(row: dict) -> str:
    """Content fingerprint of a source row.

    Re-uploading the same file is a no-op, while a genuine repeat (the same
    person registering again on another day) still lands as its own row —
    de-duplication of *people* happens later, in the metrics engine.
    """
    payload = "|".join(f"{k}={row[k]!r}" for k in sorted(row))
    return hashlib.md5(payload.encode("utf-8", "replace")).hexdigest()[:32]


def _existing_hashes(db: Session, dataset_type: str, client_id: int) -> set:
    model = MODEL_BY_TYPE.get(dataset_type)
    if model is None:
        return set()
    query = select(model.row_hash).where(model.row_hash.isnot(None))
    if hasattr(model, "client_id"):
        query = query.where(model.client_id == client_id)
    return {value for (value,) in db.execute(query).all()}


def run_ingest(db: Session, upload: RawUpload) -> RawUpload:
    """Stream the stored file into its target table. Updates `upload` in place."""
    mapping = upload.mapping or {}
    options = upload.options or {}
    dataset_type = upload.dataset_type or "custom"
    params = {**DEFAULT_METHODOLOGY, **(options.get("methodology") or {})}

    # The client is decided when the file is uploaded and is never re-derived
    # here. `client_name` used to be read from the form and fell back to a
    # hardcoded "CoachEasily", which silently dropped other orgs' files into
    # that client — and created a brand new client on any typo.
    if upload.client_id:
        client = db.get(Client, upload.client_id)
        if client is None:
            raise ValueError(f"Upload {upload.id} points at missing client {upload.client_id}")
    else:
        # Only reachable from scripts that pre-date client_id on the upload row.
        name = options.get("client_name")
        if not name:
            raise ValueError("Upload has no client — re-upload it against a client")
        client = get_or_create_client(db, name)
        upload.client_id = client.id

    upload.status = "processing"
    db.commit()

    resolver = PersonResolver(
        db,
        client.id,
        team_email_domains=params.get("team_email_domains"),
        team_name_patterns=params.get("team_name_patterns"),
        team_phones=params.get("team_phones"),
    )
    bots = BotCache(db, client.id, params)
    skip_duplicates = options.get("skip_duplicates", True)
    seen = _existing_hashes(db, dataset_type, client.id) if skip_duplicates else set()

    default_language = options.get("language") or guess_language(upload.sheet_name, upload.filename)
    generic_ds = None
    if dataset_type == "custom":
        generic_ds = _get_generic_dataset(db, client.id, upload, options)

    headers, rows = read_table(upload.stored_path, upload.sheet_name)
    total = inserted = skipped = 0
    batch: list[tuple[object, object]] = []

    for row in rows:
        total += 1
        fingerprint = row_hash(row)
        if skip_duplicates and fingerprint in seen:
            skipped += 1
            continue
        try:
            built = _build_row(
                dataset_type, row, mapping, options, params, client.id, upload,
                resolver, bots, default_language, generic_ds,
            )
        except Exception as exc:  # a single bad row must not kill the load
            skipped += 1
            if not upload.error_detail:
                upload.error_detail = f"row {total}: {exc}"
            continue

        if built is None:
            skipped += 1
            continue
        obj, person, _ = built
        obj.row_hash = fingerprint
        seen.add(fingerprint)
        batch.append((obj, person))
        if len(batch) >= BATCH:
            inserted += _flush_batch(db, batch)
            batch = []

    inserted += _flush_batch(db, batch)

    if generic_ds is not None:
        generic_ds.row_count = (generic_ds.row_count or 0) + inserted
        generic_ds.columns = headers
        db.add(generic_ds)

    upload.row_count = total
    upload.inserted_count = inserted
    upload.skipped_count = skipped
    upload.status = "success" if inserted else ("failed" if total == 0 else "partial")
    if skipped and inserted:
        upload.status = "partial"
    upload.finished_at = datetime.now()
    db.commit()
    return upload


def _flush_batch(db: Session, batch: list) -> int:
    if not batch:
        return 0
    db.flush()  # gives new Person rows their ids
    for obj, person in batch:
        if person is not None:
            obj.person_id = person.id
        db.add(obj)
    db.commit()
    return len(batch)


def _get_generic_dataset(db: Session, client_id: int, upload: RawUpload, options: dict):
    name = options.get("generic_dataset_name") or upload.generic_dataset_name or (
        upload.sheet_name or upload.filename
    )
    dataset = db.execute(
        select(GenericDataset).where(
            GenericDataset.client_id == client_id, GenericDataset.name == name
        )
    ).scalar_one_or_none()
    if dataset is None:
        dataset = GenericDataset(client_id=client_id, name=name, columns=[], row_count=0)
        db.add(dataset)
        db.flush()
    upload.generic_dataset_name = name
    return dataset


def _build_row(dataset_type, row, mapping, options, params, client_id, upload,
               resolver, bots, default_language, generic_ds):
    if dataset_type == "registrations":
        return _build_registration(row, mapping, options, client_id, upload, resolver, default_language)
    if dataset_type == "ai_calls":
        return _build_call(row, mapping, options, client_id, upload, resolver, bots)
    if dataset_type == "sales":
        return _build_sale(row, mapping, options, params, client_id, upload, resolver, default_language)
    if dataset_type == "attendance":
        return _build_attendance(row, mapping, options, client_id, upload, resolver, default_language)
    if dataset_type == "webinar_daily":
        return _build_webinar_daily(row, mapping, client_id, upload, default_language)
    return _build_generic(row, mapping, client_id, upload, resolver, generic_ds)


def _jsonable(row: dict) -> dict:
    out = {}
    for key, value in row.items():
        if value is None or isinstance(value, (int, float, bool, str)):
            out[key] = value
        else:
            out[key] = str(value)
    return out


def _build_registration(row, mapping, options, client_id, upload, resolver, default_language):
    name = clean_str(_val(row, mapping, "name"), 200)
    email = clean_str(_val(row, mapping, "email"), 200)
    phone = _val(row, mapping, "phone")
    registered_at = to_datetime(_val(row, mapping, "registered_date"), _val(row, mapping, "registered_time"))
    if not (norm_phone(phone) or norm_email(email)):
        return None
    if registered_at is None:
        return None
    person = resolver.resolve(name, email, phone)
    obj = Registration(
        client_id=client_id,
        upload_id=upload.id,
        name=name,
        email=email,
        phone=clean_str(phone, 40),
        phone_norm=norm_phone(phone),
        registered_at=registered_at,
        registration_date=registered_at.date(),
        language=clean_str(_val(row, mapping, "language"), 40) or default_language,
        program=clean_str(_val(row, mapping, "program"), 80) or options.get("program"),
        utm_source=clean_str(_val(row, mapping, "utm_source"), 120),
        utm_medium=clean_str(_val(row, mapping, "utm_medium"), 200),
        utm_campaign=clean_str(_val(row, mapping, "utm_campaign"), 200),
        utm_content=clean_str(_val(row, mapping, "utm_content"), 300),
        utm_adname=clean_str(_val(row, mapping, "utm_adname"), 300),
        salary_band=clean_str(_val(row, mapping, "salary_band"), 80),
        gender=clean_str(_val(row, mapping, "gender"), 30),
        raw=_jsonable(row) if options.get("keep_raw", True) else None,
    )
    return obj, person, (obj.phone_norm, obj.registration_date)


def _build_call(row, mapping, options, client_id, upload, resolver, bots):
    phone = _val(row, mapping, "phone")
    email = clean_str(_val(row, mapping, "email"), 200)
    name = clean_str(_val(row, mapping, "contact_name"), 200)
    if not (norm_phone(phone) or norm_email(email)):
        return None
    started_at = to_datetime(_val(row, mapping, "started_at"))
    created_at = to_datetime(_val(row, mapping, "source_created_at"))
    ended_at = to_datetime(_val(row, mapping, "ended_at"))
    stamp = started_at or created_at or ended_at
    if stamp is None:
        return None
    bot_name = clean_str(_val(row, mapping, "bot_name"), 200)
    bot = bots.get(bot_name)
    person = resolver.resolve(name, email, phone)
    call_sid = clean_str(_val(row, mapping, "call_sid"), 80)
    obj = AiCall(
        client_id=client_id,
        upload_id=upload.id,
        bot_id=bot.id if bot else None,
        bot_name=bot_name,
        contact_name=name,
        phone=clean_str(phone, 40),
        phone_norm=norm_phone(phone),
        email=email,
        status=clean_str(_val(row, mapping, "status"), 40),
        outcome=clean_str(_val(row, mapping, "outcome"), 80),
        goal_outcome=clean_str(_val(row, mapping, "goal_outcome"), 120),
        interest_level=clean_str(_val(row, mapping, "interest_level"), 60),
        sentiment=clean_str(_val(row, mapping, "sentiment"), 60),
        lead_temperature=clean_str(_val(row, mapping, "lead_temperature"), 60),
        duration_s=to_int(_val(row, mapping, "duration_s")) or 0,
        turns=to_int(_val(row, mapping, "turns")),
        red_flags=clean_str(_val(row, mapping, "red_flags"), 60),
        summary=clean_str(_val(row, mapping, "summary")),
        transcript=clean_str(_val(row, mapping, "transcript")) if options.get("keep_transcripts", True) else None,
        recording_url=clean_str(_val(row, mapping, "recording_url")),
        call_sid=call_sid,
        started_at=started_at,
        ended_at=ended_at,
        source_created_at=created_at,
        call_date=stamp.date(),
        raw=None,  # transcripts make raw JSON huge; the columns above cover it
    )
    return obj, person, call_sid or (obj.phone_norm, obj.bot_name, stamp)


def _build_sale(row, mapping, options, params, client_id, upload, resolver, default_language):
    phone = _val(row, mapping, "phone")
    email = clean_str(_val(row, mapping, "email"), 200)
    name = clean_str(_val(row, mapping, "name"), 200)
    if not (norm_phone(phone) or norm_email(email)):
        return None
    sold_at = to_datetime(_val(row, mapping, "sale_date"), _val(row, mapping, "sale_time"))
    if sold_at is None:
        return None
    amount = to_float(_val(row, mapping, "amount")) or 0.0
    if amount <= 0 and not params.get("count_zero_amount_sales", False):
        return None
    person = resolver.resolve(name, email, phone)
    obj = Sale(
        client_id=client_id,
        upload_id=upload.id,
        name=name,
        email=email,
        phone=clean_str(phone, 40),
        phone_norm=norm_phone(phone),
        amount=amount,
        sold_at=sold_at,
        sale_date=sold_at.date(),
        product=clean_str(_val(row, mapping, "product"), 120) or options.get("product"),
        payment_type=clean_str(_val(row, mapping, "payment_type"), 40) or options.get("payment_type"),
        payment_id=clean_str(_val(row, mapping, "payment_id"), 120),
        payment_status=clean_str(_val(row, mapping, "payment_status"), 60),
        language=clean_str(_val(row, mapping, "language"), 40) or default_language,
        raw=_jsonable(row) if options.get("keep_raw", True) else None,
    )
    return obj, person, (obj.phone_norm, obj.sale_date, obj.amount)


def _build_attendance(row, mapping, options, client_id, upload, resolver, default_language):
    phone = _val(row, mapping, "phone")
    email = clean_str(_val(row, mapping, "email"), 200)
    name = clean_str(_val(row, mapping, "name"), 200)
    if not (norm_phone(phone) or norm_email(email) or name):
        return None
    attended_on = to_date(_val(row, mapping, "attended_on"))
    if attended_on is None:
        return None
    person = resolver.resolve(name, email, phone)
    obj = Attendance(
        client_id=client_id,
        upload_id=upload.id,
        name=name,
        email=email,
        phone=clean_str(phone, 40),
        phone_norm=norm_phone(phone),
        attended_on=attended_on,
        minutes_in_session=to_float(_val(row, mapping, "minutes_in_session")),
        language=clean_str(_val(row, mapping, "language"), 40) or default_language,
        raw=_jsonable(row) if options.get("keep_raw", True) else None,
    )
    return obj, person, (obj.phone_norm, obj.attended_on, obj.name)


def _build_webinar_daily(row, mapping, client_id, upload, default_language):
    day = to_date(_val(row, mapping, "day"))
    if day is None:
        return None
    obj = WebinarDaily(
        client_id=client_id,
        upload_id=upload.id,
        day=day,
        language=clean_str(_val(row, mapping, "language"), 40) or default_language,
        leads=to_int(_val(row, mapping, "leads")),
        show_up=to_int(_val(row, mapping, "show_up")),
        attendees_at_pitch=to_int(_val(row, mapping, "attendees_at_pitch")),
        total_sale=to_float(_val(row, mapping, "total_sale")),
        total_lock=to_float(_val(row, mapping, "total_lock")),
        raw=_jsonable(row),
    )
    return obj, None, (obj.day, obj.language)


def _build_generic(row, mapping, client_id, upload, resolver, generic_ds):
    person = None
    if any(mapping.get(k) for k in ("phone", "email", "name")):
        person = resolver.resolve(
            _val(row, mapping, "name"), _val(row, mapping, "email"), _val(row, mapping, "phone")
        )
    obj = GenericRecord(
        dataset_id=generic_ds.id,
        upload_id=upload.id,
        row_date=to_date(_val(row, mapping, "row_date")),
        data=_jsonable(row),
    )
    return obj, person, None
