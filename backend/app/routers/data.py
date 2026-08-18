from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import distinct, func, select
from sqlalchemy.orm import Session

from ..config import DEFAULT_METHODOLOGY
from ..db import get_db
from ..deps import owned, require_client
from ..models import (
    AiCall,
    Attendance,
    Bot,
    Client,
    GenericDataset,
    GenericRecord,
    MethodologyConfig,
    Person,
    Registration,
    Sale,
    WebinarDaily,
)
from ..schemas import BotOut, BotUpdate, MethodologyIn, MethodologyOut

router = APIRouter(prefix="/api", tags=["data"])

TABLES = {
    "registrations": (Registration, Registration.registration_date),
    "ai_calls": (AiCall, AiCall.call_date),
    "sales": (Sale, Sale.sale_date),
    "attendance": (Attendance, Attendance.attended_on),
    "webinar_daily": (WebinarDaily, WebinarDaily.day),
    "persons": (Person, None),
}


@router.get("/clients")
def clients(db: Session = Depends(get_db)):
    rows = db.execute(select(Client).order_by(Client.name)).scalars().all()
    return [{"id": c.id, "name": c.name, "code": c.code} for c in rows]


@router.get("/summary")
def summary(client: Client = Depends(require_client), db: Session = Depends(get_db)):
    """Row counts and date spans for one client only."""
    out = {"client": {"id": client.id, "name": client.name}, "tables": {}, "generic_datasets": []}
    for name, (model, date_col) in TABLES.items():
        count = db.execute(
            select(func.count()).select_from(model).where(model.client_id == client.id)
        ).scalar_one()
        entry = {"rows": count}
        if date_col is not None and count:
            lo, hi = db.execute(
                select(func.min(date_col), func.max(date_col)).where(model.client_id == client.id)
            ).one()
            entry["min_date"] = lo.isoformat() if lo else None
            entry["max_date"] = hi.isoformat() if hi else None
        out["tables"][name] = entry

    datasets = db.execute(
        select(GenericDataset).where(GenericDataset.client_id == client.id)
    ).scalars()
    for ds in datasets:
        out["generic_datasets"].append(
            {"id": ds.id, "name": ds.name, "rows": ds.row_count, "columns": ds.columns}
        )

    langs = db.execute(
        select(distinct(Registration.language)).where(
            Registration.client_id == client.id, Registration.language.isnot(None)
        )
    ).scalars().all()
    out["languages"] = sorted(l for l in langs if l)
    products = db.execute(
        select(distinct(Sale.product)).where(
            Sale.client_id == client.id, Sale.product.isnot(None)
        )
    ).scalars().all()
    out["products"] = sorted(p for p in products if p)
    return out


@router.get("/rows/{table}")
def rows(table: str, limit: int = 50, offset: int = 0,
         client: Client = Depends(require_client), db: Session = Depends(get_db)):
    if table == "generic":
        # Generic records carry no client_id of their own — scope through the dataset.
        owned_ids = select(GenericDataset.id).where(GenericDataset.client_id == client.id)
        records = db.execute(
            select(GenericRecord)
            .where(GenericRecord.dataset_id.in_(owned_ids))
            .order_by(GenericRecord.id.desc())
            .limit(limit).offset(offset)
        ).scalars().all()
        return {"rows": [r.data for r in records]}
    if table not in TABLES:
        raise HTTPException(404, f"Unknown table '{table}'")
    model, _ = TABLES[table]
    total = db.execute(
        select(func.count()).select_from(model).where(model.client_id == client.id)
    ).scalar_one()
    records = db.execute(
        select(model).where(model.client_id == client.id)
        .order_by(model.id.desc()).limit(limit).offset(offset)
    ).scalars().all()
    out = []
    for record in records:
        item = {}
        for column in record.__table__.columns:
            value = getattr(record, column.name)
            if column.name in ("raw", "transcript", "summary"):
                continue
            item[column.name] = value.isoformat() if hasattr(value, "isoformat") else value
        out.append(item)
    return {"rows": out, "total": total, "limit": limit, "offset": offset}


@router.get("/bots", response_model=list[BotOut])
def bots(client: Client = Depends(require_client), db: Session = Depends(get_db)):
    return db.execute(
        select(Bot).where(Bot.client_id == client.id).order_by(Bot.name)
    ).scalars().all()


@router.patch("/bots/{bot_id}", response_model=BotOut)
def update_bot(bot_id: int, body: BotUpdate,
               client: Client = Depends(require_client), db: Session = Depends(get_db)):
    bot = owned(db.get(Bot, bot_id), client.id, "Bot")
    if body.role is not None:
        bot.role = body.role
    if body.program is not None:
        # A client running two webinars tags each bot with the one it works
        # for, so its talk time is charged to that webinar's ROI alone.
        bot.program = body.program.strip() or None
    if body.active is not None:
        bot.active = body.active
    if body.language is not None:
        bot.language = body.language
    db.commit()
    return bot


@router.get("/methodologies", response_model=list[MethodologyOut])
def methodologies(client: Client = Depends(require_client), db: Session = Depends(get_db)):
    """This client's configs, plus any shared one it can start from."""
    return db.execute(
        select(MethodologyConfig).where(
            (MethodologyConfig.client_id == client.id) | MethodologyConfig.client_id.is_(None)
        ).order_by(MethodologyConfig.client_id.is_(None), MethodologyConfig.id)
    ).scalars().all()


@router.get("/methodologies/defaults")
def methodology_defaults():
    return DEFAULT_METHODOLOGY


@router.post("/methodologies", response_model=MethodologyOut)
def create_methodology(body: MethodologyIn, client: Client = Depends(require_client),
                       db: Session = Depends(get_db)):
    existing = db.execute(
        select(MethodologyConfig).where(
            MethodologyConfig.client_id == client.id, MethodologyConfig.name == body.name
        )
    ).scalar_one_or_none()
    config = existing or MethodologyConfig(name=body.name, client_id=client.id)
    config.params = {**DEFAULT_METHODOLOGY, **body.params}
    config.description = body.description
    if body.is_default:
        # Only this client's other configs lose the flag.
        for other in db.execute(
            select(MethodologyConfig).where(MethodologyConfig.client_id == client.id)
        ).scalars():
            other.is_default = False
        config.is_default = True
    db.add(config)
    db.commit()
    return config


@router.delete("/methodologies/{config_id}")
def delete_methodology(config_id: int, db: Session = Depends(get_db)):
    config = db.get(MethodologyConfig, config_id)
    if not config:
        raise HTTPException(404, "Not found")
    db.delete(config)
    db.commit()
    return {"deleted": config_id}
