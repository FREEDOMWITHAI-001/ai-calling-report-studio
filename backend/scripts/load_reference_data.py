"""Load the real CoachEasily reference files into the database.

Usage (from backend/):
    .venv\\Scripts\\python.exe scripts\\load_reference_data.py [--reset]

Files are read from ../_reference/raw. This is the fastest way to get an
end-to-end demo: after it finishes, generate a report for 17 Jul - 14 Aug 2026.
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.db import Base, SessionLocal, engine, init_db  # noqa: E402
from app.ingest.loaders import run_ingest  # noqa: E402
from app.ingest.readers import preview  # noqa: E402
from app.ingest.schema import suggest_mapping  # noqa: E402
from app.models import RawUpload  # noqa: E402

RAW = Path(__file__).resolve().parent.parent.parent / "_reference" / "raw"
WORKBOOK = RAW / "Purushottam_Hambarde_PH__Scalex_3.xlsx"
CALL_LOG = RAW / "call-logs-2026-08-14.csv"

CLIENT = "CoachEasily"

JOBS = [
    {
        "path": WORKBOOK, "sheet": "L0 English Leads data", "type": "registrations",
        "options": {"language": "English", "program": "CBA X"},
        "overrides": {"registered_date": "Date", "registered_time": "Time", "name": "Name",
                      "email": "Email", "phone": "Number"},
    },
    {
        "path": CALL_LOG, "sheet": None, "type": "ai_calls",
        "options": {"keep_transcripts": False},
        "overrides": {"started_at": "Started At", "source_created_at": "Created At",
                      "ended_at": "Ended At", "duration_s": "Duration (s)"},
    },
    {
        "path": WORKBOOK, "sheet": "L1 English - Full and lock", "type": "sales",
        "options": {"language": "English", "product": "L1 English", "payment_type": "full_or_lock"},
        "overrides": {"sale_date": "Date", "sale_time": "Time", "amount": "Amount",
                      "name": "Name", "email": "Email", "phone": "Number"},
    },
    {
        "path": WORKBOOK, "sheet": "L1 English - Balance", "type": "sales",
        "options": {"language": "English", "product": "L1 English", "payment_type": "balance"},
        "overrides": {"sale_date": "Date", "sale_time": "Time", "amount": "Amount",
                      "name": "Name", "email": "Email", "phone": "Number"},
    },
    {
        "path": WORKBOOK, "sheet": "English Number Fetch", "type": "attendance",
        "options": {"language": "English"},
        "overrides": {"attended_on": "Date", "minutes_in_session": "Time", "name": "Name",
                      "email": "Email", "phone": "Number"},
    },
    {
        "path": WORKBOOK, "sheet": "English Webinar data", "type": "webinar_daily",
        "options": {"language": "English"},
        "overrides": {"day": "Date", "leads": "Leads", "show_up": "Show Up",
                      "attendees_at_pitch": "Attendees at Pitch"},
    },
]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--reset", action="store_true", help="drop and recreate all tables first")
    args = parser.parse_args()

    if args.reset:
        print("Dropping tables...")
        Base.metadata.drop_all(bind=engine)
    init_db()

    for job in JOBS:
        path: Path = job["path"]
        if not path.exists():
            print(f"SKIP  {path.name}: file not found")
            continue
        headers = preview(path, job["sheet"], 1)["columns"]
        mapping = suggest_mapping(job["type"], headers)
        mapping.update({k: v for k, v in job["overrides"].items() if v in headers})
        mapping = {k: v for k, v in mapping.items() if v}

        db = SessionLocal()
        try:
            upload = RawUpload(
                filename=path.name,
                stored_path=str(path),
                sheet_name=job["sheet"],
                dataset_type=job["type"],
                mapping=mapping,
                options={"client_name": CLIENT, **job["options"]},
                size_bytes=path.stat().st_size,
                status="queued",
                uploaded_by="load_reference_data",
            )
            db.add(upload)
            db.commit()
            started = time.time()
            print(f"LOAD  {job['type']:<14} {path.name} [{job['sheet'] or 'csv'}] ...", flush=True)
            run_ingest(db, upload)
            print(f"      rows={upload.row_count:,} inserted={upload.inserted_count:,} "
                  f"skipped={upload.skipped_count:,} status={upload.status} "
                  f"({time.time() - started:.1f}s)")
            if upload.error_detail:
                print(f"      first error: {upload.error_detail[:200]}")
        finally:
            db.close()


if __name__ == "__main__":
    main()
