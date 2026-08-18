from __future__ import annotations

import shutil
import uuid
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import storage
from ..config import INGEST_MODE, UPLOAD_DIR
from ..db import SessionLocal, get_db
from ..deps import owned, require_client, resolve_client
from ..ingest import readers
from ..ingest.loaders import run_ingest
from ..ingest.schema import (
    dataset_catalog,
    detect_dataset_type,
    header_signature,
    suggest_mapping,
)
from ..models import Client, MappingTemplate, RawUpload
from ..schemas import IngestRequest, UploadOut

router = APIRouter(prefix="/api/uploads", tags=["uploads"])


def _owned_upload(db: Session, upload_id: int, client_id: int) -> RawUpload:
    """A file belongs to the client it was uploaded for, from the moment it lands."""
    return owned(db.get(RawUpload, upload_id), client_id, "Upload")


def _source(db: Session, upload: RawUpload) -> Path:
    """A readable path for an upload, restored from the blob if the disk is cold."""
    try:
        return storage.local_path(
            db, upload.blob_key, upload.stored_path, Path(upload.stored_path).suffix
        )
    except FileNotFoundError as exc:
        raise HTTPException(410, str(exc))


@router.get("/datasets")
def datasets():
    return dataset_catalog()


@router.get("", response_model=list[UploadOut])
def list_uploads(client: Client = Depends(require_client), db: Session = Depends(get_db),
                 limit: int = 100):
    return db.execute(
        select(RawUpload).where(RawUpload.client_id == client.id)
        .order_by(RawUpload.id.desc()).limit(limit)
    ).scalars().all()


@router.post("", response_model=dict)
async def create_upload(
    file: UploadFile = File(...),
    client_id: int = Form(..., description="Organisation this file belongs to"),
    db: Session = Depends(get_db),
):
    """Store a file *against a client*.

    The client is fixed here, at upload time — not guessed later from a name in
    the ingest form. That is what stops a file landing in the wrong org.
    """
    client = resolve_client(db, client_id)

    suffix = Path(file.filename or "upload").suffix.lower()
    if suffix not in {".csv", ".xlsx", ".xlsm", ".tsv", ".txt"}:
        raise HTTPException(400, f"Unsupported file type '{suffix}'. Upload CSV or XLSX.")
    stored = UPLOAD_DIR / f"{uuid.uuid4().hex}{suffix}"
    with stored.open("wb") as out:
        shutil.copyfileobj(file.file, out)

    # Disk alone is not durable on a serverless host, so the bytes are also kept
    # in the database and every later read goes through storage.local_path.
    try:
        blob_key = storage.put(
            db, stored.read_bytes(), file.filename or stored.name, file.content_type
        )
    except ValueError as exc:
        stored.unlink(missing_ok=True)
        raise HTTPException(413, str(exc))

    upload = RawUpload(
        filename=file.filename or stored.name,
        stored_path=str(stored),
        blob_key=blob_key,
        content_type=file.content_type,
        size_bytes=stored.stat().st_size,
        client_id=client.id,
        status="uploaded",
    )
    db.add(upload)
    db.commit()

    try:
        sheets = readers.list_sheets(stored)
        if not readers.is_excel(stored) and sheets:
            sheets[0]["name"] = upload.filename  # show the user's own filename, not the stored uuid
    except Exception as exc:
        upload.status = "failed"
        upload.error_detail = str(exc)
        db.commit()
        raise HTTPException(400, f"Could not read file: {exc}")

    return {
        "id": upload.id,
        "filename": upload.filename,
        "size_bytes": upload.size_bytes,
        "client": {"id": client.id, "name": client.name},
        "sheets": sheets,
        "is_excel": readers.is_excel(stored),
    }


@router.get("/{upload_id}/preview")
def preview_upload(upload_id: int, sheet: str | None = None, limit: int = 15,
                   client: Client = Depends(require_client), db: Session = Depends(get_db)):
    upload = _owned_upload(db, upload_id, client.id)
    try:
        data = readers.preview(_source(db, upload), sheet, limit)
    except Exception as exc:
        raise HTTPException(400, f"Could not preview: {exc}")

    headers = data["columns"]
    detected, confidence = detect_dataset_type(headers, sheet, upload.filename)
    signature = header_signature(headers)
    template = db.execute(
        select(MappingTemplate).where(MappingTemplate.signature == signature)
        .order_by(MappingTemplate.use_count.desc())
    ).scalars().first()

    mapping = template.mapping if template else suggest_mapping(detected, headers)
    if template:
        detected = template.dataset_type
        confidence = 1.0
    return {
        "columns": headers,
        "rows": data["rows"],
        "suggested_type": detected,
        "confidence": round(confidence, 3),
        "suggested_mapping": mapping,
        "mapping_options": {
            key: suggest_mapping(key, headers) for key in
            ("registrations", "ai_calls", "sales", "attendance", "webinar_daily", "custom")
        },
        "template_used": template.name if template else None,
        "signature": signature,
    }


def _ingest_task(upload_id: int) -> None:
    db = SessionLocal()
    try:
        upload = db.get(RawUpload, upload_id)
        if upload:
            run_ingest(db, upload)
    except Exception as exc:  # keep the failure visible in the uploads log
        db.rollback()
        upload = db.get(RawUpload, upload_id)
        if upload:
            upload.status = "failed"
            upload.error_detail = str(exc)[:4000]
            upload.finished_at = datetime.now()
            db.commit()
    finally:
        db.close()


@router.post("/{upload_id}/ingest", response_model=UploadOut)
def ingest_upload(upload_id: int, body: IngestRequest, background: BackgroundTasks,
                  client: Client = Depends(require_client), db: Session = Depends(get_db)):
    # The target org comes from the upload row, which was fixed at upload time.
    # There is no client name in the ingest payload to get wrong.
    upload = _owned_upload(db, upload_id, client.id)

    upload.dataset_type = body.dataset_type
    upload.sheet_name = body.sheet
    upload.mapping = {k: v for k, v in body.mapping.items() if v}
    upload.options = {
        "language": body.language,
        "program": body.program,
        "product": body.product,
        "payment_type": body.payment_type,
        "generic_dataset_name": body.generic_dataset_name,
        "skip_duplicates": body.skip_duplicates,
        "keep_raw": body.keep_raw,
        "keep_transcripts": body.keep_transcripts,
    }
    upload.status = "queued"
    upload.error_detail = None
    db.commit()

    if body.save_template_as:
        headers = list({v for v in upload.mapping.values() if v})
        signature = header_signature(
            readers.preview(_source(db, upload), body.sheet, 1)["columns"]
        )
        template = MappingTemplate(
            name=body.save_template_as,
            dataset_type=body.dataset_type,
            signature=signature,
            mapping=upload.mapping,
            use_count=1,
        )
        db.add(template)
        db.commit()

    if INGEST_MODE == "inline":
        _ingest_task(upload.id)
        db.refresh(upload)
    else:
        background.add_task(_ingest_task, upload.id)
    return upload


@router.get("/{upload_id}", response_model=UploadOut)
def get_upload(upload_id: int, client: Client = Depends(require_client),
               db: Session = Depends(get_db)):
    return _owned_upload(db, upload_id, client.id)


@router.delete("/{upload_id}")
def delete_upload(upload_id: int, client: Client = Depends(require_client),
                  db: Session = Depends(get_db)):
    upload = _owned_upload(db, upload_id, client.id)
    path = Path(upload.stored_path)
    if path.exists():
        path.unlink()
    storage.delete(db, upload.blob_key, path.suffix)
    db.delete(upload)
    db.commit()
    return {"deleted": upload_id}
