"""Compose a finished report: cohort -> sections -> a renderable document.

This is the whole pipeline for the new formats. Given a client, a window and a
template, it produces a plain dict that any renderer can walk. No renderer is
involved here, and no template-specific logic either.
"""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy.orm import Session

from ..metrics.cohort import Cohort
from . import sections as section_lib
from .templates import Template, get_template


def compose(
    db: Session,
    client_id: int,
    client_name: str,
    date_from: date,
    date_to: date,
    template: Template | str | None = None,
    params: dict | None = None,
    language: str | None = None,
    program: str | None = None,
    title: str | None = None,
) -> dict:
    if not isinstance(template, Template):
        template = get_template(template)

    cohort = Cohort(
        db, client_id=client_id, date_from=date_from, date_to=date_to,
        params=params, language=language, program=program,
    )

    built = []
    for ref in template.sections:
        config = dict(ref.config)
        if ref.title:
            config["title"] = ref.title
        built.append(section_lib.build_section(ref.key, cohort, config).to_dict())

    skipped = [s for s in built if not s["available"]]

    return {
        "meta": {
            "title": title or f"{client_name} — {template.label}",
            "client_id": client_id,
            "client": client_name,
            "template": template.key,
            "template_label": template.label,
            "cover_title": template.cover_title,
            "cover": template.cover,
            "date_from": date_from.isoformat(),
            "date_to": date_to.isoformat(),
            "window_days": cohort.window_days,
            "language": language,
            "program": program,
            "generated_at": datetime.now().isoformat(timespec="seconds"),
            "params": cohort.params,
        },
        "brand": template.brand.__dict__,
        "sections": built,
        # Stated plainly rather than silently omitted, so a thin report is
        # obviously a data problem and not a calculation problem.
        "skipped": [{"key": s["key"], "title": s["title"], "reason": s["unavailable_reason"]}
                    for s in skipped],
        "totals": {
            "registrants": len(cohort.registrants),
            "dialled": len(cohort.dialled),
            "connected": len(cohort.connected),
            "reached": len(cohort.reached),
            "attended": len(cohort.attended),
            "buyers": len(cohort.buyers),
            "calls_placed": cohort.calls_placed,
            "billed_minutes": cohort.billed_minutes,
            "talk_cost": cohort.talk_cost,
            "revenue": cohort.revenue_total,
        },
    }
