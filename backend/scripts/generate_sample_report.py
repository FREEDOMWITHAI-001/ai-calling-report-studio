"""Generate PDF + Excel + PPTX for one window straight from the database.

    .venv\\Scripts\\python.exe scripts\\generate_sample_report.py 2026-07-17 2026-08-14
"""
from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select  # noqa: E402

from app.config import REPORT_DIR  # noqa: E402
from app.db import SessionLocal  # noqa: E402
from app.metrics.engine import compute_report  # noqa: E402
from app.models import Client  # noqa: E402
from app.render.excel import build_excel  # noqa: E402
from app.render.pdf import build_pdf  # noqa: E402
from app.render.pptx_deck import build_pptx  # noqa: E402


def main() -> None:
    start = date.fromisoformat(sys.argv[1]) if len(sys.argv) > 1 else date(2026, 7, 17)
    end = date.fromisoformat(sys.argv[2]) if len(sys.argv) > 2 else date(2026, 8, 14)
    language = sys.argv[3] if len(sys.argv) > 3 else "English"

    db = SessionLocal()
    client = db.execute(select(Client).order_by(Client.id)).scalars().first()
    if not client:
        print("No data loaded. Run load_reference_data.py first.")
        return
    result = compute_report(db, client.id, start, end, language=language, title="CBA X · English")
    stem = f"CBA-X_{start}_{end}"
    outputs = [
        build_excel(result, Path(REPORT_DIR) / f"{stem}.xlsx"),
        build_pdf(result, Path(REPORT_DIR) / f"{stem}.pdf"),
        build_pptx(result, Path(REPORT_DIR) / f"{stem}.pptx"),
    ]
    for path in outputs:
        print(f"  {path}  ({path.stat().st_size:,} bytes)")
    db.close()


if __name__ == "__main__":
    main()
