from __future__ import annotations

import traceback
from datetime import date, datetime
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import storage
from ..config import REPORT_DIR
from ..db import SessionLocal, get_db
from ..deps import owned, require_client, resolve_client
from ..metrics.engine import compute_report
from ..models import Client, MethodologyConfig, ReportRun
from ..render.excel import build_excel
from ..render.pdf import build_pdf
from ..render.pptx_deck import build_pptx
from ..render.workbook import build_workbook
from ..reports import compose, describe_all, resolve_for_client
from ..schemas import BatchReportRequest, ReportOut, ReportRequest

router = APIRouter(prefix="/api/reports", tags=["reports"])

BUILDERS = {"xlsx": build_excel, "pdf": build_pdf, "pptx": build_pptx}
EXTENSIONS = {"xlsx": ".xlsx", "pdf": ".pdf", "pptx": ".pptx"}
MEDIA = {
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "pdf": "application/pdf",
    "pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
}


def _resolve_client(db: Session, client_id: int | None) -> Client:
    """Reports are always for one named client.

    This used to fall back to "the first client by id", which meant any request
    that forgot `client_id` quietly produced a CoachEasily report — and showed
    CoachEasily's numbers to whoever asked.
    """
    return resolve_client(db, client_id)


def _resolve_params(db: Session, body: ReportRequest, client_id: int | None = None) -> dict:
    """Methodology for this run: format defaults, then the saved config, then
    whatever the caller overrode. The format is lowest so a client that has
    settled a question keeps its answer."""
    params: dict = {}
    if client_id is not None and body.use_template:
        params.update(resolve_for_client(db, client_id, body.template).params or {})
    config = None
    if body.methodology_id:
        config = db.get(MethodologyConfig, body.methodology_id)
    if config is None and client_id is not None:
        # This client's own answer wins over the shared one.
        config = db.execute(
            select(MethodologyConfig).where(
                MethodologyConfig.client_id == client_id,
                MethodologyConfig.is_default.is_(True),
            )
        ).scalars().first()
    if config is None:
        config = db.execute(
            select(MethodologyConfig).where(
                MethodologyConfig.client_id.is_(None),
                MethodologyConfig.is_default.is_(True),
            )
        ).scalars().first()
    if config:
        params.update(config.params or {})
    if body.params_override:
        params.update(body.params_override)
    return params


def _default_title(client: Client, body: ReportRequest) -> str:
    bits = [body.language or "", body.program or ""]
    label = " ".join(b for b in bits if b).strip()
    return body.title or (f"{label}" if label else client.name)


@router.get("/templates")
def list_templates():
    """The report formats available. A client picks one; sections follow from it."""
    return describe_all()


@router.post("/compose")
def compose_report(body: ReportRequest, db: Session = Depends(get_db)):
    """Build a client-format report as structured sections, without writing files.

    This is the new pipeline: cohort -> sections -> blocks. Sections whose inputs
    are missing come back marked unavailable with the reason, rather than as
    zeros that look like findings.
    """
    client = _resolve_client(db, body.client_id)
    return compose(
        db,
        client_id=client.id,
        client_name=client.name,
        date_from=body.date_from,
        date_to=body.date_to,
        template=body.template,
        params=_resolve_params(db, body, client.id),
        language=body.language,
        program=body.program,
        title=body.title,
    )


@router.post("/preview")
def preview_report(body: ReportRequest, db: Session = Depends(get_db)):
    """Compute the numbers without writing any files (drives the dashboard)."""
    client = _resolve_client(db, body.client_id)
    return compute_report(
        db,
        client_id=client.id,
        date_from=body.date_from,
        date_to=body.date_to,
        params=_resolve_params(db, body, client.id),
        language=body.language,
        program=body.program,
        bot_names=body.bot_names,
        product=body.product,
        title=_default_title(client, body),
    )


def _generate(run_id: int) -> None:
    db = SessionLocal()
    try:
        run = db.get(ReportRun, run_id)
        if not run:
            return
        run.status = "running"
        db.commit()

        filters = run.filters or {}
        template = filters.get("template")

        if template:
            # Client-format path: cohort -> sections -> blocks -> renderer.
            client = db.get(Client, run.client_id)
            result = compose(
                db,
                client_id=run.client_id,
                client_name=client.name if client else "",
                date_from=run.date_from,
                date_to=run.date_to,
                template=resolve_for_client(db, run.client_id, template),
                params=filters.get("params") or {},
                language=filters.get("language"),
                program=filters.get("program"),
                title=run.title,
            )
            builders = {"xlsx": build_workbook}
        else:
            result = compute_report(
                db,
                client_id=run.client_id,
                date_from=run.date_from,
                date_to=run.date_to,
                params=filters.get("params") or {},
                language=filters.get("language"),
                program=filters.get("program"),
                bot_names=filters.get("bot_names"),
                product=filters.get("product"),
                title=run.title,
            )
            builders = BUILDERS

        files = []
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        safe = "".join(c if c.isalnum() or c in "-_ " else "_" for c in run.title).strip().replace(" ", "-")
        for fmt in (run.formats or ["xlsx"]):
            builder = builders.get(fmt)
            if not builder:
                continue
            filename = f"{safe or 'report'}_{run.date_from}_{run.date_to}_{stamp}{EXTENSIONS[fmt]}"
            target = Path(REPORT_DIR) / filename
            builder(result, target)
            # The rendered file is kept in the database so the download works
            # from any instance, not just the one that happened to build it.
            blob_key = storage.put(db, target.read_bytes(), filename, MEDIA.get(fmt))
            files.append({
                "format": fmt,
                "filename": filename,
                "path": str(target),
                "blob_key": blob_key,
                "size_bytes": target.stat().st_size,
            })

        run.metrics = result
        run.files = files
        run.status = "success"
        run.finished_at = datetime.now()
        db.commit()
    except Exception as exc:
        db.rollback()
        run = db.get(ReportRun, run_id)
        if run:
            run.status = "failed"
            run.error_detail = f"{exc}\n{traceback.format_exc()[:3000]}"
            run.finished_at = datetime.now()
            db.commit()
    finally:
        db.close()


def _create_run(db: Session, body: ReportRequest) -> ReportRun:
    client = _resolve_client(db, body.client_id)
    if body.date_from > body.date_to:
        raise HTTPException(400, "date_from must be on or before date_to")

    # `use_template=False` opts back into the original webinar-uplift report.
    # Otherwise the client's own default format is used when none is named, so
    # "generate a report" means "generate it in this client's format".
    template = None
    if body.use_template:
        template = resolve_for_client(db, client.id, body.template)

    # A client format currently renders to a workbook only; the legacy report
    # keeps all three outputs. Silently dropping a requested format would be
    # worse than saying so, so the run records what it will actually produce.
    allowed = {"xlsx"} if template else set(BUILDERS)
    formats = [f for f in body.formats if f in allowed] or ["xlsx"]

    run = ReportRun(
        title=_default_title(client, body),
        client_id=client.id,
        methodology_id=body.methodology_id,
        date_from=body.date_from,
        date_to=body.date_to,
        formats=formats,
        template_key=template.key if template else None,
        template_label=template.label if template else "Webinar uplift (original)",
        filters={
            "template": template.key if template else None,
            "language": body.language,
            "program": body.program,
            "product": body.product,
            "bot_names": body.bot_names,
            "params": _resolve_params(db, body, client.id),
        },
        status="queued",
    )
    db.add(run)
    db.commit()
    return run


@router.post("", response_model=ReportOut)
def create_report(body: ReportRequest, background: BackgroundTasks, db: Session = Depends(get_db)):
    run = _create_run(db, body)
    background.add_task(_generate, run.id)
    return run


@router.post("/batch", response_model=list[ReportOut])
def create_batch(body: BatchReportRequest, background: BackgroundTasks, db: Session = Depends(get_db)):
    runs = []
    for item in body.ranges:
        run = _create_run(db, item)
        background.add_task(_generate, run.id)
        runs.append(run)
    return runs


@router.get("", response_model=list[ReportOut])
def list_reports(limit: int = 50, template: str | None = None,
                 client: Client = Depends(require_client), db: Session = Depends(get_db)):
    """Every report generated for this client, newest first.

    All formats are returned by default — selecting a format for the next report
    does not hide the reports that came before it. Pass `?template=` only when
    you deliberately want one format's history.
    """
    query = select(ReportRun).where(ReportRun.client_id == client.id)
    if template:
        query = query.where(ReportRun.template_key == template)
    return db.execute(query.order_by(ReportRun.id.desc()).limit(limit)).scalars().all()


@router.get("/{run_id}")
def get_report(run_id: int, include_metrics: bool = True,
               client: Client = Depends(require_client), db: Session = Depends(get_db)):
    run = owned(db.get(ReportRun, run_id), client.id, "Report")
    payload = {
        "id": run.id,
        "title": run.title,
        "date_from": run.date_from,
        "date_to": run.date_to,
        "template_key": run.template_key,
        "template_label": run.template_label,
        "formats": run.formats,
        "status": run.status,
        "error_detail": run.error_detail,
        "files": run.files,
        "filters": run.filters,
        "generated_at": run.generated_at,
        "finished_at": run.finished_at,
    }
    if include_metrics:
        payload["metrics"] = run.metrics
    return payload


@router.get("/{run_id}/download/{fmt}")
def download_report(run_id: int, fmt: str, client: Client = Depends(require_client),
                    db: Session = Depends(get_db)):
    run = owned(db.get(ReportRun, run_id), client.id, "Report")
    if not run.files:
        raise HTTPException(404, "Report file not found")
    for item in run.files:
        if item["format"] == fmt:
            try:
                path = storage.local_path(
                    db, item.get("blob_key"), item.get("path"), EXTENSIONS[fmt]
                )
            except FileNotFoundError:
                raise HTTPException(410, "File is no longer available")
            return FileResponse(path, media_type=MEDIA[fmt], filename=item["filename"])
    raise HTTPException(404, f"No '{fmt}' output for this report")


@router.delete("/{run_id}")
def delete_report(run_id: int, client: Client = Depends(require_client),
                  db: Session = Depends(get_db)):
    run = owned(db.get(ReportRun, run_id), client.id, "Report")
    for item in run.files or []:
        path = Path(item["path"])
        if path.exists():
            path.unlink()
        storage.delete(db, item.get("blob_key"), EXTENSIONS.get(item["format"], ""))
    db.delete(run)
    db.commit()
    return {"deleted": run_id}


@router.get("/presets/ranges")
def presets():
    today = date.today()
    def iso(d: date) -> str:
        return d.isoformat()
    month_start = today.replace(day=1)
    return [
        {"key": "last_7", "label": "Last 7 days", "date_from": iso(date.fromordinal(today.toordinal() - 6)), "date_to": iso(today)},
        {"key": "last_14", "label": "Last 14 days", "date_from": iso(date.fromordinal(today.toordinal() - 13)), "date_to": iso(today)},
        {"key": "last_30", "label": "Last 30 days", "date_from": iso(date.fromordinal(today.toordinal() - 29)), "date_to": iso(today)},
        {"key": "this_month", "label": "This month", "date_from": iso(month_start), "date_to": iso(today)},
    ]
