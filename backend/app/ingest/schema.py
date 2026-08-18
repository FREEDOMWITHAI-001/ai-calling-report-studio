"""Canonical dataset definitions + auto-detection of type and column mapping.

The upload flow is deliberately generic: any CSV/XLSX can be pushed at the app.
These definitions only drive the *suggested* mapping shown in the UI — the user
can always override, or send the file to the generic store instead.
"""
from __future__ import annotations

import hashlib
import re

from ..util.normalize import norm_name


# `program` on attendance and sales is deliberately given no synonyms. Auto-
# mapping it grabbed whatever column looked programme-ish — a Zoom "Topic", a
# sales "registered for webinar" — and tagged every row with a value that does
# not equal the label the registrations use. The report then scoped to "HBL",
# matched nothing, and reported zero show-ups and zero buyers as though they
# were findings. It is set from the upload's Program field, or mapped by hand.


class Field:
    def __init__(self, key: str, label: str, synonyms: list[str], required: bool = False,
                 kind: str = "text"):
        self.key = key
        self.label = label
        self.synonyms = synonyms
        self.required = required
        self.kind = kind

    def as_dict(self) -> dict:
        return {
            "key": self.key,
            "label": self.label,
            "required": self.required,
            "kind": self.kind,
            "synonyms": self.synonyms,
        }


DATASETS: dict[str, dict] = {
    "registrations": {
        "label": "Registration data",
        "table": "registrations",
        "description": "Workshop / webinar sign-ups. One row per registration.",
        "sheet_hints": ["leads data", "registration", "l0 ", "signup", "sign up"],
        "fields": [
            Field("name", "Name", ["name", "contact name", "full name", "lead name"], True),
            Field("email", "Email", ["email", "email id", "e-mail"]),
            Field("phone", "Phone", ["phone", "number", "mobile", "contact number", "phone number"], True),
            # The date this person is a lead *for* — the webinar they signed up
            # to attend. A contact-creation date ("date added") is a different
            # thing and must not win: filing leads under the day their record
            # was created scatters them across dates no webinar ran on.
            Field("registered_date", "Webinar / registration date",
                  ["webinar date", "session date", "masterclass date", "event date",
                   "registration date", "registered date", "registered at",
                   "registered on", "signup date", "sign up date", "reg date",
                   "date", "created at"], True, "date"),
            Field("registered_time", "Registration time", ["time", "registration time"], False, "time"),
            Field("event_name", "Event / workshop name",
                  ["workshop name", "event name", "webinar name", "masterclass"]),
            Field("language", "Language / segment", ["language", "segment", "batch"]),
            Field("program", "Program / brand", ["brand", "program", "product", "course"]),
            Field("utm_source", "UTM source", ["utm source", "source"]),
            Field("utm_medium", "UTM medium", ["utm medium"]),
            Field("utm_campaign", "UTM campaign", ["utm campaign"]),
            Field("utm_content", "UTM content", ["utm content"]),
            Field("utm_adname", "UTM ad name", ["utm adname", "ad name"]),
            Field("salary_band", "Salary band", ["salary", "income"]),
            Field("gender", "Gender", ["gender"]),
        ],
    },
    "ai_calls": {
        "label": "AI calling data",
        "table": "ai_calls",
        "description": "Bot call logs — one row per placed call.",
        "sheet_hints": ["call log", "call-logs", "calls", "ai call"],
        "fields": [
            Field("bot_name", "Bot name", ["bot name", "bot", "agent", "assistant"], True),
            Field("contact_name", "Contact name", ["contact name", "name", "lead name"]),
            Field("phone", "Phone", ["phone", "number", "mobile", "to number"], True),
            Field("email", "Email", ["email", "email id"]),
            Field("status", "Call status", ["status", "call status"], True),
            Field("outcome", "Outcome", ["outcome", "call outcome"]),
            Field("goal_outcome", "Goal outcome", ["goal outcome"]),
            Field("interest_level", "Interest level", ["interest level", "interest"]),
            Field("sentiment", "Sentiment", ["sentiment"]),
            Field("lead_temperature", "Lead temperature", ["lead temperature", "temperature"]),
            Field("duration_s", "Duration (seconds)", ["duration (s)", "duration", "talk time", "call duration"], True, "number"),
            Field("turns", "Turns", ["turns"], False, "number"),
            Field("red_flags", "Red flags", ["red flags"]),
            Field("summary", "Summary", ["summary"]),
            Field("transcript", "Transcript", ["transcript"]),
            Field("recording_url", "Recording URL", ["recording url", "recording"]),
            Field("call_sid", "Call SID", ["call sid", "call id", "sid"]),
            Field("started_at", "Started at", ["started at", "start time", "call date"], True, "datetime"),
            Field("ended_at", "Ended at", ["ended at", "end time"], False, "datetime"),
            Field("source_created_at", "Created at", ["created at"], False, "datetime"),
        ],
    },
    "sales": {
        "label": "Sales data",
        "table": "sales",
        "description": "Purchases / payments, tied back to a registrant.",
        "sheet_hints": ["full and lock", "balance", "sales", "l1 ", "buyers", "payment"],
        "fields": [
            Field("name", "Name", ["name", "customer name"], True),
            Field("email", "Email", ["email", "email id"]),
            Field("phone", "Phone", ["phone", "number", "mobile"], True),
            Field("amount", "Amount", ["amount", "payment amount", "value"], True, "number"),
            Field("sale_date", "Sale date", ["date", "date of l1", "payment date"], True, "date"),
            Field("sale_time", "Sale time", ["time", "time of l1"], False, "time"),
            Field("payment_id", "Payment ID", ["payment id", "transaction id", "order id"]),
            Field("payment_status", "Payment status", ["payment status full l1", "status", "payment status"]),
            Field("product", "Product", ["product", "course", "offer"]),
            Field("program", "Webinar / programme", []),  # never auto-mapped: see below
            Field("payment_type", "Payment type", ["payment type", "type"]),
            Field("language", "Language / segment", ["language", "segment"]),
        ],
    },
    "attendance": {
        "label": "Attendance / Zoom data",
        "table": "attendance",
        "description": "Who actually showed up, one row per attendance record.",
        "sheet_hints": ["number fetch", "attendee", "attendance", "zoom"],
        "fields": [
            Field("name", "Name", ["name", "attendee name", "name (original name)"], True),
            Field("email", "Email", ["email", "email id"]),
            # Not required: Zoom exports identify an attendee by name and email
            # and carry no phone at all. One of name/email/phone is enough to
            # resolve the person, which is what the loader actually enforces.
            Field("phone", "Phone", ["number", "phone", "mobile"]),
            Field("attended_on", "Attended on", ["date", "date of workshop", "workshop date", "join time", "attended on", "attendance date", "attended date", "attended"], True, "date"),
            Field("program", "Webinar / programme", []),  # never auto-mapped: see below
            Field("minutes_in_session", "Minutes in session", ["time", "time in session", "duration", "minutes"], False, "number"),
            Field("language", "Language / segment", ["language", "segment"]),
        ],
    },
    "webinar_daily": {
        "label": "Platform daily numbers",
        "table": "webinar_daily",
        "description": "The platform's own per-day counts, used for reconciliation only.",
        "sheet_hints": ["webinar data", "daily", "lead count"],
        "fields": [
            Field("day", "Date", ["date", "day"], True, "date"),
            Field("leads", "Leads", ["leads", "registrations"], False, "number"),
            Field("show_up", "Show up", ["show up", "showed", "show-up"], False, "number"),
            Field("attendees_at_pitch", "Attendees at pitch", ["attendees at pitch", "at pitch"], False, "number"),
            Field("total_sale", "Total sale", ["total sale"], False, "number"),
            Field("total_lock", "Total lock", ["total lock"], False, "number"),
            Field("language", "Language / segment", ["language", "segment"]),
        ],
    },
    "custom": {
        "label": "Other / custom data",
        "table": "generic_records",
        "description": "Anything else — stored as-is and queryable, with optional person linking.",
        "sheet_hints": [],
        "fields": [
            Field("name", "Name (optional link)", ["name"]),
            Field("email", "Email (optional link)", ["email"]),
            Field("phone", "Phone (optional link)", ["phone", "number", "mobile"]),
            Field("row_date", "Row date (optional)", ["date"], False, "date"),
        ],
    },
}


def dataset_catalog() -> list[dict]:
    return [
        {
            "key": key,
            "label": cfg["label"],
            "table": cfg["table"],
            "description": cfg["description"],
            "fields": [f.as_dict() for f in cfg["fields"]],
        }
        for key, cfg in DATASETS.items()
    ]


def _clean_header(header: str) -> str:
    return re.sub(r"[^a-z0-9 ]", " ", str(header).lower()).strip()


def _match_score(header: str, synonyms: list[str]) -> float:
    cleaned = _clean_header(header)
    if not cleaned:
        return 0.0
    compact = cleaned.replace(" ", "")
    best = 0.0
    for syn in synonyms:
        syn_clean = _clean_header(syn)
        syn_compact = syn_clean.replace(" ", "")
        if not syn_compact:
            continue
        if compact == syn_compact:
            best = max(best, 1.0)
        elif compact.startswith(syn_compact) or syn_compact.startswith(compact):
            best = max(best, 0.8)
        elif syn_compact in compact:
            best = max(best, 0.65)
    return best


def suggest_mapping(dataset_type: str, headers: list[str]) -> dict[str, str | None]:
    """Best-effort {canonical_field: source_column} for the given headers."""
    cfg = DATASETS.get(dataset_type)
    if not cfg:
        return {}
    mapping: dict[str, str | None] = {}
    used: set[str] = set()
    scored: list[tuple[float, str, str]] = []
    for field in cfg["fields"]:
        for header in headers:
            score = _match_score(header, field.synonyms)
            if score > 0:
                scored.append((score, field.key, header))
    scored.sort(key=lambda item: (-item[0], item[1]))
    for score, field_key, header in scored:
        if field_key in mapping or header in used:
            continue
        mapping[field_key] = header
        used.add(header)
    for field in cfg["fields"]:
        mapping.setdefault(field.key, None)
    return mapping


def detect_dataset_type(headers: list[str], sheet_name: str | None = None,
                        filename: str | None = None) -> tuple[str, float]:
    """Score each known dataset type against headers + name hints.

    The second term measures how much of *the file* a type explains, not how
    much of the type the file fills. Scoring against `len(fields)` handed the
    win to whichever schema was smallest: a registration export with 9 columns
    matched name+phone under `attendance` (4 of its 6 fields, 0.67) and lost to
    its own type (8 of 15 fields, 0.61), despite explaining nearly every column.
    Dividing by the header count removes that bias — the type that accounts for
    more of the file wins, regardless of how many fields it declares.
    """
    hint_text = " ".join(filter(None, [str(sheet_name or ""), str(filename or "")])).lower()
    header_count = max(1, len([h for h in headers if str(h or "").strip()]))
    best_key, best_score = "custom", 0.0
    for key, cfg in DATASETS.items():
        if key == "custom":
            continue
        fields = cfg["fields"]
        required = [f for f in fields if f.required]
        mapping = suggest_mapping(key, headers)
        matched_required = sum(1 for f in required if mapping.get(f.key))
        matched_any = sum(1 for f in fields if mapping.get(f.key))
        if required and matched_required < max(2, len(required) - 1):
            score = 0.0
        else:
            score = 0.6 * (matched_required / max(1, len(required))) + 0.4 * (
                min(matched_any, header_count) / header_count
            )
        for hint in cfg["sheet_hints"]:
            if hint in hint_text:
                score += 0.35
                break
        if score > best_score:
            best_key, best_score = key, score
    if best_score < 0.45:
        return "custom", best_score
    return best_key, min(best_score, 1.0)


def header_signature(headers: list[str]) -> str:
    joined = "|".join(sorted(_clean_header(h) for h in headers if h))
    return hashlib.sha256(joined.encode("utf-8")).hexdigest()[:32]


def guess_language(*texts: str | None) -> str | None:
    """Pull a language/segment label out of a sheet or bot name."""
    blob = " ".join(t for t in texts if t).lower()
    for lang in ("english", "hinglish", "hindi", "marathi", "superwomen", "super women", "tamil", "telugu"):
        if lang in blob:
            return "SuperWomen" if "women" in lang else lang.capitalize()
    return None


def looks_like_person(name: str | None) -> bool:
    return bool(norm_name(name))
