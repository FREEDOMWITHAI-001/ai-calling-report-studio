---
name: report-studio
description: Context and operating rules for the CoachEasily Report Studio in this folder — the FastAPI + React app that ingests registration / AI-calling / sales / attendance files and generates the "WHAT AI CALLING ADDED" report as PDF, Excel and PPTX. Load this before touching the metrics engine, the renderers, the ingestion pipeline, the database, or before starting/debugging the app. Triggers on: report studio, AI calling report, CBA X, ROI report, talk cost, connected leads, uplift, methodology, ingest a file, generate a report, validate the engine.
---

# CoachEasily Report Studio

Full written record: `PROJECT-NOTES.txt` (plain text) and `README.md` (documentation).
Read `PROJECT-NOTES.txt` first if you need detail beyond this file.

## Non-negotiable rules

1. **The published reference reports are ground truth.** After ANY change to
   `backend/app/metrics/engine.py`, `backend/app/ingest/persons.py`, or
   `backend/app/ingest/loaders.py`, run:
   ```
   cd backend && .\.venv\Scripts\python.exe scripts\validate_against_reference.py
   ```
   The 17 Jul – 14 Aug 2026 window must stay within ~1% on every headline number
   (ROI 14.6×, revenue with AI ₹776,889, 111 buyers, 1,248 connected). If a change
   moves those numbers, it is wrong until proven otherwise.

2. **Never hardcode a business constant.** Sale value, cost per minute, connect
   threshold, band edges, bot patterns, team/test patterns all live in
   `DEFAULT_METHODOLOGY` in `backend/app/config.py` and are overridable per report
   via `methodology_configs`. New constants go there too.

3. **Person matching precedence is phone → email → name, and name is only trusted
   when the row has no usable phone.** Relaxing this merges different people who
   share a common name (it cost ~100 registrants in an early run). Tightening it
   breaks attendance matching (that export has "Not Found" numbers and platform
   alias emails, so name is the only handle). See `backend/app/ingest/persons.py`.

4. **Ingestion is idempotent by row content hash**, not by natural key. Re-uploading
   the same file must insert nothing; a genuine repeat registration must still land.

5. **Don't add a dependency without checking it has a Python 3.14 wheel.** The venv
   is Python 3.14; pandas/numpy were deliberately avoided.

## Running it

```powershell
.\run.ps1 -Prod    # everything on http://127.0.0.1:8000  (UI is prebuilt)
.\run.ps1          # API :8000 + hot-reload Vite UI on :5173
.\setup.ps1        # first time only
```

`ERR_CONNECTION_REFUSED` on :5173 almost always means Vite is not running — use
:8000 or start `run.ps1`. Health check: `http://127.0.0.1:8000/api/health`.

## Database

Dev PostgreSQL (host/user/password in `backend/.env`, which is gitignored), in the
dedicated schema **`ai_report`** (devdb's `public` holds 217 tables from other
projects — never write there). Config in `backend/.env`; the `@` in the password is
`%40` inside the URL. Removing `DATABASE_URL` falls back to SQLite at
`backend/data/app.db`.

## Where things live

| Task | File |
|---|---|
| The calculation | `backend/app/metrics/engine.py` |
| Statistics (z-test, rates) | `backend/app/metrics/stats.py` |
| Excel / PDF / PPTX output | `backend/app/render/{excel,pdf,pptx_deck}.py` |
| Shared formatting + method text | `backend/app/render/style.py` |
| File parsing, type + column detection | `backend/app/ingest/{readers,schema}.py` |
| Person resolution | `backend/app/ingest/persons.py` |
| Writing to tables | `backend/app/ingest/loaders.py` |
| API | `backend/app/routers/{uploads,data,reports}.py` |
| Schema | `backend/app/models.py` |
| UI | `frontend/src/pages/` |

## Scripts

```
backend\scripts\load_reference_data.py --reset      # reload all reference data (~2.5 min)
backend\scripts\validate_against_reference.py       # engine vs published reports
backend\scripts\generate_sample_report.py 2026-07-17 2026-08-14
```

## The known data gap

The supplied `call-logs-2026-08-14.csv` only covers ~17 Jul 2026 onward. The
26 Jun – 17 Jul window therefore under-reports talk cost (₹3,172 vs the published
₹12,337) because ~2,300 calls and the whole day-of bot are missing. This is a data
gap, not a bug — if the user brings the older call log, ingest it through the Upload
page and re-validate. Do not "fix" the engine to compensate.
