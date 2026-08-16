r"""Bind each client to its own report format.

Idempotent: matched on (client, key). Re-running updates in place.

    cd backend && .\.venv\Scripts\python.exe scripts\seed_report_formats.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select  # noqa: E402

from app.db import SessionLocal, init_db  # noqa: E402
from app.models import Client, ReportFormat  # noqa: E402

FOOTER = "Prepared by FWAI"
COVER = "What AI calling added"

# Clients whose format we have actually seen. These keep their own layout.
SPECIFIC: list[tuple[str, str, str, str, str]] = [
    ("DVA", "dva-bootcamp", "DVA bootcamp report", "bootcamp", "5B3FE8"),
    ("CBH", "cbh-leadlist", "CBH lead-list report", "lead_list", "0E8F6A"),
]

# Everyone else gets the common format. Add a name here and re-run.
COMMON_CLIENTS = [
    "CoachEasily", "Nikunj", "Priyank", "Rahul",
    "Easyparentinghub.com", "Energy Queens", "Flute Gandharvas",
    "Freedomwitai", "Freedom With AI", "gonatureclassrooms.org",
    "My Health School",
]


def _slug(name: str) -> str:
    out = "".join(ch.lower() if ch.isalnum() else "-" for ch in name)
    while "--" in out:
        out = out.replace("--", "-")
    return out.strip("-")[:44]


def _bindings() -> list[tuple[str, str, str, str, dict]]:
    rows = [
        (client, key, name, base,
         {"cover_title": COVER, "brand": {"accent": accent, "footer": FOOTER},
          "formats": ["xlsx"]})
        for client, key, name, base, accent in SPECIFIC
    ]
    named = {c for c, *_ in SPECIFIC}
    for client in COMMON_CLIENTS:
        if client in named:
            continue
        rows.append((
            client, f"{_slug(client)}-standard", f"{client} standard report", "webinar",
            {"cover_title": COVER, "brand": {"accent": "1D4ED8", "footer": FOOTER},
             "formats": ["xlsx"]},
        ))
    return rows


BINDINGS = _bindings()


def main() -> None:
    init_db()
    db = SessionLocal()
    clients = {c.name: c for c in db.execute(select(Client)).scalars()}
    created = updated = missing = 0

    for client_name, key, name, base_key, spec in BINDINGS:
        client = clients.get(client_name)
        if client is None:
            print(f"  ? {client_name:<14} no such client — skipped")
            missing += 1
            continue

        record = db.execute(
            select(ReportFormat).where(
                ReportFormat.client_id == client.id, ReportFormat.key == key
            )
        ).scalars().first()
        verb = "~"
        if record is None:
            record = ReportFormat(client_id=client.id, key=key)
            db.add(record)
            created += 1
            verb = "+"
        else:
            updated += 1

        record.name = name
        record.base_key = base_key
        record.spec = spec
        record.description = f"{client_name}'s own report format."

        # One default per client.
        for other in db.execute(
            select(ReportFormat).where(ReportFormat.client_id == client.id)
        ).scalars():
            other.is_default = False
        record.is_default = True
        print(f"  {verb} {client_name:<14} {key} (base: {base_key}) -> default")

    db.commit()
    print(f"\ncreated={created} updated={updated} missing={missing}")


if __name__ == "__main__":
    main()
