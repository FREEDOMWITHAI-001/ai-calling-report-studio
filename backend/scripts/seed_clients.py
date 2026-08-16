r"""Seed the ai_report.clients table with the Wavelength v3 organization list.

Idempotent: matches on clients.name (unique), inserts what is missing and fills in
code/notes on rows that already exist. Safe to re-run.

    cd backend && .\.venv\Scripts\python.exe scripts\seed_clients.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.db import SessionLocal  # noqa: E402
from app.models import Client  # noqa: E402

# (display name, short code, role as shown in the Wavelength org switcher)
ORGANIZATIONS: list[tuple[str, str, str]] = [
    ("CBH", "cbh", "client user"),
    ("CoachEasily", "coacheasily", "client user"),
    ("DVA", "dva", "client user"),
    ("Easyparentinghub.com", "easyparentinghub", "client user"),
    ("Energy Queens", "energy-queens", "client user"),
    ("Flute Gandharvas", "flute-gandharvas", "client user"),
    ("Freedomwitai", "freedomwitai", "client admin"),
    ("Freedom With AI", "freedom-with-ai", "client user"),
    ("gonatureclassrooms.org", "gonatureclassrooms", "client user"),
    ("My Health School", "my-health-school", "client user"),
    ("Priyank", "priyank", "client user"),
    ("Rahul", "rahul", "client user"),
    ("tewt", "tewt", "client user"),
]


def main() -> None:
    session = SessionLocal()
    existing = {c.name: c for c in session.query(Client).all()}
    inserted = updated = 0

    for name, code, role in ORGANIZATIONS:
        note = f"Wavelength v3 organization ({role})"
        client = existing.get(name)
        if client is None:
            session.add(Client(name=name, code=code, notes=note))
            inserted += 1
            print(f"  + {name}")
        elif client.code != code or client.notes != note:
            client.code = code
            client.notes = note
            updated += 1
            print(f"  ~ {name}")

    session.commit()
    print(f"\ninserted={inserted} updated={updated} total={session.query(Client).count()}")


if __name__ == "__main__":
    main()
