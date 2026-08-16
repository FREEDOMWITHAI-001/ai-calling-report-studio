"""Application configuration.

Postgres is used when DATABASE_URL is set (e.g.
postgresql+psycopg://user:pass@localhost/reports); otherwise the app falls back
to a local SQLite file so it runs with zero infrastructure setup on Windows.
"""
from __future__ import annotations

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent          # backend/
PROJECT_DIR = BASE_DIR.parent                              # project root
DATA_DIR = Path(os.getenv("DATA_DIR", BASE_DIR / "data"))
UPLOAD_DIR = DATA_DIR / "uploads"
REPORT_DIR = DATA_DIR / "reports"

for _d in (DATA_DIR, UPLOAD_DIR, REPORT_DIR):
    _d.mkdir(parents=True, exist_ok=True)

def _load_env_file() -> None:
    """Minimal .env loader so no extra dependency is needed."""
    env_path = BASE_DIR / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


_load_env_file()

DATABASE_URL = os.getenv("DATABASE_URL") or f"sqlite:///{(DATA_DIR / 'app.db').as_posix()}"
# Postgres only: keep this app's tables in their own schema so a shared dev
# database stays uncluttered.
DB_SCHEMA = os.getenv("DB_SCHEMA", "ai_report") if DATABASE_URL.startswith("postgres") else None

APP_NAME = "CoachEasily Report Studio"
CURRENCY = "₹"

# Default methodology parameters, taken from the reference reports
# (17 Jul - 14 Aug 2026 edition, which supersedes the earlier one).
DEFAULT_METHODOLOGY = {
    "sale_value": 6999.0,
    "cost_per_minute": 5.10,
    "connect_threshold_s": 15,          # "connected" = talk strictly greater than 15s
    # The client workbooks split contact into two levels and report both:
    #   connected = the call was answered at all (talk > 0s)
    #   reached   = answered AND talked past this threshold — "a real conversation"
    # Defaulting to connect_threshold_s keeps "reached" identical to what the
    # original engine called "connected", so existing numbers do not move.
    "reach_threshold_s": 15,
    "billing_rounding": "ceil_minute",  # ceil_minute | exact_second
    "baseline_mode": "not_connected",   # not_connected | never_dialled | no_bot_reached
    "uplift_mode": "weighted",          # weighted (lead-age bands) | simple
    "age_band_edges": [0, 3, 7, 10, 14],  # 0-2, 3-6, 7-9, 10-13, 14+
    "signup_bot_patterns": ["instant confirmation"],
    "dayof_bot_patterns": ["session today"],
    "cost_bot_scope": "signup_and_dayof",  # signup_and_dayof | all_bots
    "team_email_domains": ["freedomwithai.com", "scalex.club"],
    "team_name_patterns": ["test user", "test ", "scalex"],
    "team_phones": [],
    "attendance_match_mode": "window",  # window | same_day
    "attendance_match_days": 1,
    "restrict_bots_to_language": True,
    "count_zero_amount_sales": False,
    "drop_sales_before_registration": True,
    "match_keys": ["phone", "email", "name"],
}
