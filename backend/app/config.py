"""Application configuration.

Postgres is used when DATABASE_URL is set (e.g.
postgresql+psycopg://user:pass@localhost/reports); otherwise the app falls back
to a local SQLite file so it runs with zero infrastructure setup on Windows.
"""
from __future__ import annotations

import os
import tempfile
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent          # backend/
PROJECT_DIR = BASE_DIR.parent                              # project root


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


# Loaded before anything reads the environment, so DATA_DIR and DATABASE_URL in
# a local .env are honoured. Real environment variables still win.
_load_env_file()


def _writable_data_dir() -> Path:
    """Pick a directory we can actually write to.

    On a normal machine this is backend/data. On a serverless host (Vercel,
    Lambda) the deployment is read-only and only the system temp dir accepts
    writes, so fall back there instead of dying at import time. Nothing here is
    the source of truth either way — durable bytes live in the database via
    `app.storage`; these directories are only a scratch/cache area.
    """
    for candidate in (Path(os.getenv("DATA_DIR", BASE_DIR / "data")),
                      Path(tempfile.gettempdir()) / "report-studio"):
        try:
            for sub in (candidate, candidate / "uploads", candidate / "reports"):
                sub.mkdir(parents=True, exist_ok=True)
            probe = candidate / ".write-test"
            probe.write_text("ok", encoding="utf-8")
            probe.unlink()
            return candidate
        except OSError:
            continue
    raise RuntimeError("No writable data directory available")


DATA_DIR = _writable_data_dir()
UPLOAD_DIR = DATA_DIR / "uploads"
REPORT_DIR = DATA_DIR / "reports"

DATABASE_URL = os.getenv("DATABASE_URL") or f"sqlite:///{(DATA_DIR / 'app.db').as_posix()}"
# Postgres only: keep this app's tables in their own schema so a shared dev
# database stays uncluttered.
DB_SCHEMA = os.getenv("DB_SCHEMA", "ai_report") if DATABASE_URL.startswith("postgres") else None

# Serverless instances are frozen the moment a response is sent, so work queued
# with BackgroundTasks may never run. On such a host the ingest is done inline
# instead — slower to respond, but it actually finishes. Override with
# INGEST_MODE=background|inline.
_default_ingest = "inline" if os.getenv("VERCEL") or os.getenv("AWS_LAMBDA_FUNCTION_NAME") else "background"
INGEST_MODE = os.getenv("INGEST_MODE", _default_ingest).strip().lower()

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
    # {programme label: substrings that identify its bots by name}. A client
    # running one webinar leaves this empty and nothing changes.
    "program_bot_patterns": {},
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
