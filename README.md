# CoachEasily Report Studio

An internal web app that ingests raw business data (registrations, AI calling logs, sales,
attendance, or anything else), stores it in normalized PostgreSQL tables, and generates the
"WHAT AI CALLING ADDED" report for any date range as **PDF, Excel and PowerPoint**.

The metrics engine is a reimplementation of the two reference reports, and it reproduces the
published 17 Jul – 14 Aug 2026 report to within **1% on every headline number** (see
[Validation](#validation)).

---

## Run it

```powershell
.\setup.ps1     # once: venv + pip install + npm install + create tables
.\run.ps1       # every time: API on :8000, UI on :5173
```

Then open **http://127.0.0.1:5173**.

For a single-process deployment (UI served by the API, no Vite):

```powershell
.\run.ps1 -Prod          # builds the UI, then serves everything at http://127.0.0.1:8000
```

Requirements: Python 3.11+ (tested on 3.14) and Node 18+ (tested on 24). No Docker, no Redis.

### Database

`backend\.env` currently points at the shared dev PostgreSQL and keeps every table in its own
schema (`ai_report`) so it cannot collide with the 217 tables already in `public`:

```
DATABASE_URL=postgresql+psycopg://<user>:<password>@<host>:5432/devdb
DB_SCHEMA=ai_report
```

Delete or comment out `DATABASE_URL` and the app falls back to a local SQLite file
(`backend\data\app.db`) with no server at all — handy for offline work.

### Load the real reference data (optional but recommended)

```powershell
cd backend
.\.venv\Scripts\python.exe scripts\load_reference_data.py --reset      # ~2.5 min
.\.venv\Scripts\python.exe scripts\validate_against_reference.py       # engine vs published reports
.\.venv\Scripts\python.exe scripts\generate_sample_report.py 2026-07-17 2026-08-14
```

This reads the three real files in `_reference\raw\` (already downloaded from the shared Drive
folder) and loads 12,856 registrations, 41,810 calls, 549 sales, 15,738 attendance rows and 999
platform-daily rows.

---

## Using the app

**Upload data** — drop in any CSV/XLSX. The app lists the sheets, previews the rows, guesses the
data type and the column mapping, and lets you correct both before loading. Mapping choices can be
saved as a reusable template keyed on the file's header signature, so the same export is one click
next time. Everything lands in the `raw_uploads` log with row/inserted/skipped counts and the first
error. Re-uploading an identical file inserts nothing (rows carry a content hash), while a genuine
repeat registration is still stored.

**Data** — browse the normalized tables the reports are built from.

**Reports** — pick a window (or a preset), optionally a language/segment and specific bots, tick
PDF / Excel / PowerPoint, then *Preview numbers* to see the whole report on screen before exporting.
`POST /api/reports/batch` generates several windows at once. Every generated file is kept with its
metadata and can be re-downloaded without recomputing.

**Methodology** — every constant the report depends on (₹6,999 sale value, ₹5.10/min, the 15-second
connect threshold, per-minute rounding, baseline definition, lead-age bands, team/test patterns, bot
role patterns) is editable, saved as a named config, and stamped into each generated report.

---

## The data model

| Table | Holds |
|---|---|
| `clients`, `events`, `bots` | Who the data belongs to, which workshop, which bot (role: signup / day_of / other) |
| `persons` | One row per human, resolved across every file by phone → email → name |
| `registrations` | Sign-ups: name, email, phone, registration date/time, UTM, language, program |
| `ai_calls` | One row per call: bot, contact, status, outcome, sentiment, duration, turns, timestamps, recording |
| `sales` | Purchases: amount, date, payment id/status/type, product |
| `attendance` | Zoom/webinar attendance rows with minutes in session |
| `webinar_daily` | The platform's own daily counts, used only for reconciliation |
| `generic_datasets` / `generic_records` | Any data type without a first-class table yet — stored as JSON, still person-linked |
| `raw_uploads`, `mapping_templates` | Upload audit log and remembered column mappings |
| `methodology_configs`, `report_runs` | Saved calculation settings and every generated report |

All tables carry `created_at` / `updated_at`. The join key across datasets is the phone number
(normalized to the last 10 digits), with email and then name as fallbacks — name is only trusted
when the row has no usable phone, which is exactly the attendance export's situation ("Not Found"
numbers and platform alias emails).

---

## How the report is calculated

1. **Registrants** — rows in the window, team/test rows removed, deduplicated to people.
2. **Connected** — a signup or day-of bot held a conversation longer than 15 s. Groups (signup,
   day-of, both) overlap by design; the baseline is everyone the bots never got talking to.
3. **Show-up** — per-person match against the attendance data.
4. **Buyers** — per-person match against sales; every buyer counts as one full sale, and sale rows
   dated before the person registered are dropped.
5. **Extra sales credited to AI** — registrants are split into lead-age bands (0-2, 3-6, 7-9, 10-13,
   14+ days). Inside each band connected leads are compared only with baseline leads of the same
   age, and the band's buy-rate gap is multiplied by that band's connected count. Summing the bands
   gives a like-for-like weighted figure instead of comparing two different mixes of lead age.
6. **Talk cost** — only in-scope bots, only calls with talk time, each call rounded **up** to the
   next whole minute (billing is per minute) × ₹5.10.
7. **Revenue with AI** = buyers × ₹6,999. **AI added** = extra sales × ₹6,999. **Without AI** =
   with − added. **ROI** = added ÷ talk cost. Significance comes from a two-proportion z-test.

Each report also carries the audit block: row counts in/out, repeat and team rows removed,
sale rows dropped and why, call match rate, exact vs billed minutes, and the observational caveat.

---

## Validation

`scripts\validate_against_reference.py` compares the engine against the published reports.
For the 17 Jul – 14 Aug 2026 window:

| Metric | Published | Engine | Diff |
|---|---:|---:|---:|
| Registrants | 2,624 | 2,626 | +0.1% |
| Connected people | 1,248 | 1,248 | 0.0% |
| Baseline people | 1,376 | 1,378 | +0.1% |
| Showed | 1,293 | 1,282 | −0.9% |
| Buyers | 111 | 111 | 0.0% |
| Calls placed | 7,268 | 7,287 | +0.3% |
| Calls connected | 1,888 | 1,889 | +0.1% |
| Billed minutes | 4,555 | 4,558 | +0.1% |
| Talk cost | ₹23,230 | ₹23,246 | +0.1% |
| Extra sales | 48.6 | 48.6 | +0.1% |
| Revenue with AI | ₹776,889 | ₹776,889 | 0.0% |
| AI added | ₹340,260 | ₹340,479 | +0.1% |
| **ROI** | **14.6×** | **14.6×** | +0.3% |

The per-group table matches almost exactly (published 1,145 / 507 / 404 / 1,376 registrants and
75 / 46 / 42 / 32 buyers; engine 1,145 / 507 / 404 / 1,378 and 75 / 46 / 42 / 32).

The residual few tenths of a percent come from the reference report's extra hand-curation — an
18-entry team/test list against this app's pattern rules, and a slightly wider cross-file name
merge. Both are configurable under **Methodology**.

---

## Known gaps and assumptions

1. **The June–July window cannot be reproduced from the supplied call log.** For 26 Jun – 17 Jul
   2026, registrants (2,047 vs 2,056) and show-up (1,018 vs 1,018) match, but the call log
   `call-logs-2026-08-14.csv` contains only 613 signup-bot calls in that window against the ~2,900
   implied by report 1, and no day-of bot calls at all — so talk cost comes out at ₹3,172 instead of
   ₹12,337. The export appears to be truncated for the earlier period. **Upload the older call log
   and that window will reproduce too.** Nothing in the code is specific to either window.
2. **Report 1 vs report 2 methodology.** Report 1 used a simpler "no bot reached" baseline and an
   unweighted lift; report 2 uses the not-connected baseline and the lead-age-weighted lift. Report 2
   is the default because it is the later and more defensible method; report 1's variant is available
   by switching `baseline_mode` / `uplift_mode` under Methodology.
3. **Report 2's Overview tab references a weighted-band table that is not actually on that tab.**
   This app renders it (Excel Overview and PDF), which is what the method text describes.
4. **Show-up matching** counts any attendance row inside the report window for that person
   (`attendance_match_mode = window`, matching the reference). Set it to `same_day` to require the
   attendance date to be the registration date.
5. **Sales are counted as one full ₹6,999 sale per person**, exactly as the reference reports do —
   lock + balance rows for the same person collapse to one sale, and zero-amount rows are dropped.
   If part payments should ever be counted at their actual amount, that is a one-line change in the
   engine plus a new methodology flag.
6. **Attendee's Report Masterdata is deliberately not loaded.** Report 2 rejected it (it matches ~7%
   of registrants); `English Number Fetch` is used instead. The file is in `_reference\raw\` if you
   want to compare.
7. **No authentication**, as requested. The app binds to 127.0.0.1; anyone who can reach the port can
   read the uploaded PII. Add a reverse proxy or ask for login to be switched on before exposing it.
8. **Background work uses FastAPI background tasks**, not Celery. A 20 MB / 33k-row call log ingests
   in ~45 s and a report renders in under a second, so a broker is not yet earning its keep. The
   ingestion and report entry points are already isolated functions, so moving them to Celery later
   is a drop-in change.
9. **Retention**: nothing is deleted automatically. Uploads live in `backend\data\uploads`, generated
   reports in `backend\data\reports`, and both have DELETE endpoints. Say the word and a scheduled
   cleanup can be added.
10. **Multi-language**: only English data has been loaded, but the Hinglish / Marathi / SuperWomen
    sheets in the same workbook load through exactly the same mapping screen, and reports filter by
    language with per-language bot scoping.

---

## Project layout

```
backend/
  app/
    config.py            methodology defaults, paths, .env loading
    db.py  models.py     SQLAlchemy engine + the normalized schema
    ingest/              readers (CSV/XLSX streaming), type+column detection,
                         person resolution, loaders
    metrics/             the report engine + statistics
    render/              excel.py, pdf.py, pptx_deck.py, shared style
    routers/             uploads, data, reports  (FastAPI)
  scripts/               load_reference_data, validate_against_reference,
                         generate_sample_report
frontend/src/            React + MUI: Dashboard, Upload, Data, Reports, Methodology
_reference/              the two sample reports + the three raw source files
```

API docs are live at http://127.0.0.1:8000/docs while the server runs.
