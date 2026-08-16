"""Compare the engine's output against the published reference reports.

Run after load_reference_data.py:
    .venv\\Scripts\\python.exe scripts\\validate_against_reference.py
"""
from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.db import SessionLocal  # noqa: E402
from app.metrics.engine import compute_report  # noqa: E402
from app.models import Client  # noqa: E402
from sqlalchemy import select  # noqa: E402

EXPECTED = {
    "report 2 (17 Jul - 14 Aug 2026)": {
        "window": (date(2026, 7, 17), date(2026, 8, 14)),
        "values": {
            "registrants": 2624,
            "connected_people": 1248,
            "baseline_people": 1376,
            "showed": 1293,
            "buyers": 111,
            "calls_placed": 7268,
            "calls_with_audio": 2548,
            "calls_connected": 1888,
            "talk_seconds": 181479,
            "billed_minutes": 4555,
            "talk_cost": 23230,
            "extra_sales": 48.6,
            "revenue_with_ai": 776889,
            "revenue_added": 340260,
            "roi": 14.6,
        },
    },
    "report 1 (26 Jun - 17 Jul 2026)": {
        "window": (date(2026, 6, 26), date(2026, 7, 17)),
        "values": {
            "registrants": 2056,
            "showed": 1018,
            "buyers": 70,
            "talk_cost": 12337,
        },
    },
}


def main() -> None:
    db = SessionLocal()
    client = db.execute(select(Client).order_by(Client.id)).scalars().first()
    if not client:
        print("No client rows — run load_reference_data.py first.")
        return

    for label, spec in EXPECTED.items():
        start, end = spec["window"]
        result = compute_report(db, client.id, start, end, language="English", title="CBA X · English")
        actual = {
            **{k: v for k, v in result["headline"].items()},
            **{k: v for k, v in result["calls"].items() if not isinstance(v, dict)},
        }
        print(f"\n=== {label} ===")
        print(f"{'metric':<22}{'expected':>14}{'actual':>14}{'diff %':>10}")
        for key, expected in spec["values"].items():
            got = actual.get(key)
            if got is None:
                print(f"{key:<22}{expected:>14,}{'n/a':>14}")
                continue
            diff = (got - expected) / expected * 100 if expected else 0
            flag = "" if abs(diff) < 2 else ("  <-- off" if abs(diff) < 10 else "  <== WAY OFF")
            print(f"{key:<22}{expected:>14,.1f}{got:>14,.1f}{diff:>9.1f}%{flag}")

        groups = result["groups"]
        print("\n  groups:")
        for key in ("total", "signup", "day_of", "both", "baseline"):
            g = groups[key]
            print(f"    {g['label']:<32} n={g['registrants']:>6,}  showed={g['showed']:>6,} "
                  f"({g['show_rate']*100:5.1f}%)  buyers={g['buyers']:>4,} ({g['buy_rate']*100:5.2f}%)")
        print(f"  audit: {result['audit']}")
        print(f"  bots in window: {list(result['calls']['bots_in_window'].items())[:6]}")
    db.close()


if __name__ == "__main__":
    main()
