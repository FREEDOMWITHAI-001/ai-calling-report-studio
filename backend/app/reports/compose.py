"""Compose a finished report: cohort -> sections -> a renderable document.

This is the whole pipeline for the new formats. Given a client, a window and a
template, it produces a plain dict that any renderer can walk. No renderer is
involved here, and no template-specific logic either.
"""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy.orm import Session

from sqlalchemy import select

from ..metrics.cohort import Cohort
from ..models import Registration
from . import sections as section_lib
from .templates import Template, get_template


def _programmes(db: Session, client_id: int, date_from: date, date_to: date,
                language: str | None) -> list[str]:
    """The programmes that actually have registrations in this window."""
    query = select(Registration.program).where(
        Registration.client_id == client_id,
        Registration.registration_date >= date_from,
        Registration.registration_date <= date_to,
        Registration.program.is_not(None),
    ).distinct()
    if language:
        query = query.where(Registration.language == language)
    return sorted({p for (p,) in db.execute(query).all() if p and str(p).strip()})


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

    # The format's own methodology, with anything explicitly passed on top.
    params = {**template.params, **(params or {})}

    cohort = Cohort(
        db, client_id=client_id, date_from=date_from, date_to=date_to,
        params=params, language=language, program=program,
    )

    built = []
    grouped: list[str] = []
    if template.group_by == "program" and not program:
        # One webinar per sheet. Each gets its own cohort, so its bots, its
        # cost and its ROI are its own — the whole point of the grouped format.
        grouped = _programmes(db, client_id, date_from, date_to, language)

    if grouped:
        per_programme = [
            (name, Cohort(db, client_id=client_id, date_from=date_from, date_to=date_to,
                          params=params, language=language, program=name))
            for name in grouped
        ]
        if template.overview_section:
            built.append(section_lib.build_section(
                template.overview_section, cohort,
                {"title": "Overview", "programmes": per_programme},
            ).to_dict())
        for name, sub in per_programme:
            for ref in template.sections:
                config = dict(ref.config)
                config["title"] = f"{name} report"
                config["program"] = name
                built.append(section_lib.build_section(ref.key, sub, config).to_dict())
    else:
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
            "grouped_by": template.group_by if grouped else None,
            "programmes": grouped or None,
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
