"""File bytes that survive a restart.

Uploads and generated reports used to live only on local disk, addressed by
absolute path. That works on one long-lived machine and fails on a serverless
host, where the instance that wrote a file is rarely the instance asked to read
it back — the download 404s, or worse, silently disappears between deploys.

So the bytes go in the database and the filesystem becomes a cache. Callers that
need a real path (openpyxl, csv readers, FileResponse) ask `local_path` for one
and get a file that is guaranteed to exist, restored from the blob if the local
copy is missing.
"""
from __future__ import annotations

import uuid
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from .config import UPLOAD_DIR
from .models import FileBlob

# How big a file we are willing to hold in a single row. Postgres handles this
# comfortably; the limit exists to turn "the request hung" into a clear error.
MAX_BLOB_BYTES = 60 * 1024 * 1024


def put(db: Session, data: bytes, filename: str, content_type: str | None = None) -> str:
    """Store bytes and return the key that addresses them."""
    if len(data) > MAX_BLOB_BYTES:
        raise ValueError(
            f"File is {len(data) // 1024 // 1024} MB; the limit is "
            f"{MAX_BLOB_BYTES // 1024 // 1024} MB."
        )
    key = uuid.uuid4().hex
    db.add(FileBlob(
        key=key,
        filename=filename,
        content_type=content_type,
        size_bytes=len(data),
        data=data,
    ))
    db.commit()
    return key


def get(db: Session, key: str) -> FileBlob | None:
    return db.execute(select(FileBlob).where(FileBlob.key == key)).scalars().first()


def local_path(db: Session, key: str | None, fallback: str | None = None,
               suffix: str = "") -> Path:
    """Return a path that exists on this machine.

    `fallback` is the legacy `stored_path` recorded before blobs existed, so
    rows written by the old code keep working as long as their file is still
    there.
    """
    if key:
        cached = Path(UPLOAD_DIR) / f"{key}{suffix}"
        if cached.exists() and cached.stat().st_size > 0:
            return cached
        blob = get(db, key)
        if blob is not None:
            cached.parent.mkdir(parents=True, exist_ok=True)
            cached.write_bytes(blob.data)
            return cached

    if fallback:
        legacy = Path(fallback)
        if legacy.exists():
            return legacy

    raise FileNotFoundError("The stored file is no longer available.")


def delete(db: Session, key: str | None, suffix: str = "") -> None:
    if not key:
        return
    blob = get(db, key)
    if blob is not None:
        db.delete(blob)
    cached = Path(UPLOAD_DIR) / f"{key}{suffix}"
    if cached.exists():
        cached.unlink()
