"""Per-client report formats.

Every route is scoped to one client, and a format defined for one client is not
reachable from another — the same rule the rest of the API follows.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import owned, require_client
from ..models import Client, ReportFormat
from ..reports.sections import registry
from ..reports.templates import BUILT_IN, DEFAULT_TEMPLATE_KEY, describe_all, from_record

router = APIRouter(prefix="/api/report-formats", tags=["formats"])


class FormatIn(BaseModel):
    key: str = Field(min_length=1, max_length=60)
    name: str = Field(min_length=1, max_length=160)
    base_key: str = DEFAULT_TEMPLATE_KEY
    description: str | None = None
    spec: dict = Field(default_factory=dict)
    is_default: bool = False


def _out(record: ReportFormat) -> dict:
    template = from_record(record)
    return {
        "id": record.id,
        "key": record.key,
        "name": record.name,
        "base_key": record.base_key,
        "description": record.description,
        "is_default": record.is_default,
        "formats": template.formats,
        "sections": [{"key": s.key, "title": s.title} for s in template.sections],
        "brand": template.brand.__dict__,
        "source": "client",
    }


@router.get("/library")
def section_library():
    """Every section that can be placed in a format, and what data it needs."""
    return [
        {
            "key": d.key,
            "title": d.title,
            "requires": list(d.requires),
            "description": d.description,
        }
        for d in registry().values()
    ]


@router.get("/built-in")
def built_in():
    """The stock layouts a client format can start from."""
    return describe_all()


@router.get("")
def list_formats(client: Client = Depends(require_client), db: Session = Depends(get_db)):
    """This client's formats, with the built-ins listed after them as fallbacks."""
    records = db.execute(
        select(ReportFormat).where(ReportFormat.client_id == client.id)
        .order_by(ReportFormat.is_default.desc(), ReportFormat.name)
    ).scalars().all()

    out = [_out(r) for r in records]
    has_default = any(r.is_default for r in records)
    for template in BUILT_IN.values():
        out.append({
            "id": None,
            "key": template.key,
            "name": template.label,
            "base_key": template.key,
            "description": template.description,
            # With no client format marked default, the built-in default is what
            # a report will actually use — say so rather than leaving it implied.
            "is_default": (not has_default) and template.key == DEFAULT_TEMPLATE_KEY,
            "formats": template.formats,
            "sections": [{"key": s.key, "title": s.title} for s in template.sections],
            "brand": template.brand.__dict__,
            "source": "built-in",
        })
    return out


@router.post("")
def upsert_format(body: FormatIn, client: Client = Depends(require_client),
                  db: Session = Depends(get_db)):
    if body.base_key not in BUILT_IN:
        raise HTTPException(400, f"Unknown base format '{body.base_key}'")

    known = set(registry())
    unknown = [s.get("key") for s in body.spec.get("sections", []) if s.get("key") not in known]
    if unknown:
        raise HTTPException(400, f"Unknown section(s): {', '.join(map(str, unknown))}")

    record = db.execute(
        select(ReportFormat).where(
            ReportFormat.client_id == client.id, ReportFormat.key == body.key
        )
    ).scalars().first()
    if record is None:
        record = ReportFormat(client_id=client.id, key=body.key)
        db.add(record)

    record.name = body.name
    record.base_key = body.base_key
    record.description = body.description
    record.spec = body.spec

    if body.is_default:
        for other in db.execute(
            select(ReportFormat).where(ReportFormat.client_id == client.id)
        ).scalars():
            other.is_default = False
        record.is_default = True

    db.commit()
    return _out(record)


@router.post("/{format_id}/default")
def make_default(format_id: int, client: Client = Depends(require_client),
                 db: Session = Depends(get_db)):
    record = owned(db.get(ReportFormat, format_id), client.id, "Report format")
    for other in db.execute(
        select(ReportFormat).where(ReportFormat.client_id == client.id)
    ).scalars():
        other.is_default = False
    record.is_default = True
    db.commit()
    return _out(record)


@router.delete("/{format_id}")
def delete_format(format_id: int, client: Client = Depends(require_client),
                  db: Session = Depends(get_db)):
    record = owned(db.get(ReportFormat, format_id), client.id, "Report format")
    db.delete(record)
    db.commit()
    return {"deleted": format_id}
