# Resume prompt — paste this into Claude Code tomorrow

Open a terminal in `D:\FWAI\FWAI-Internal\AI Calling report System` and paste the block below.

---

```
Continue work on the CoachEasily Report Studio in this folder. It is already built and working —
read README.md first, then RESUME-PROMPT.md for where we left off. Do not rebuild from scratch.

State as of 16 Aug 2026:
- Backend: FastAPI + SQLAlchemy in backend/app, venv at backend\.venv (Python 3.14).
- Frontend: React + MUI + Vite in frontend/ (already npm installed and built).
- Database: dev PostgreSQL, schema "ai_report" (connection details in backend\.env).
  Loaded: 12,856 registrations, 41,810 AI calls, 549 sales, 15,738 attendance, 999 platform-daily.
- The metrics engine reproduces the published 17 Jul - 14 Aug 2026 report to within 1% on every
  headline number (ROI 14.6x, revenue with AI Rs 776,889, 111 buyers). Proof:
  backend\scripts\validate_against_reference.py — run it before and after any engine change.

Start the app:   .\run.ps1        then open http://127.0.0.1:5173

Today's tasks (in priority order — confirm with me before starting anything below):
1. Walk me through the UI and let me test upload -> report generation myself.
2. <add whatever you want changed here>

Known gaps documented in README.md "Known gaps and assumptions" — the important one is #1:
the supplied call log only covers ~17 Jul onward, so the 26 Jun - 17 Jul window cannot be fully
reproduced. If I bring the older call log, ingest it via the Upload page and re-validate.
```

---

## Quick reference for tomorrow

**Start / stop**

```powershell
.\run.ps1              # API :8000 + UI :5173 (hot reload)
.\run.ps1 -Prod        # build UI once, serve everything from :8000
```

**Useful scripts** (from `backend\`, using `.\.venv\Scripts\python.exe`)

| Script | What it does |
|---|---|
| `scripts\load_reference_data.py --reset` | Wipes and reloads all reference data (~2.5 min) |
| `scripts\validate_against_reference.py` | Engine vs the two published reports |
| `scripts\generate_sample_report.py 2026-07-17 2026-08-14` | Writes PDF+XLSX+PPTX to `backend\data\reports` |

**Where things live**

- Calculation logic: `backend\app\metrics\engine.py`
- Report styling: `backend\app\render\{excel,pdf,pptx_deck,style}.py`
- File parsing + column detection: `backend\app\ingest\`
- Methodology defaults: `backend\app\config.py` (`DEFAULT_METHODOLOGY`)
- UI pages: `frontend\src\pages\`

**Open questions still worth deciding**

1. Do you have the older call log (covering 26 Jun – 17 Jul 2026)? That is the only thing blocking
   full reproduction of report 1.
2. Should Hinglish / Marathi / SuperWomen data be loaded now? Same workbook, same upload screen.
3. Retention: keep uploads and generated reports forever, or auto-clean after N days?
4. Does this stay on localhost, or does it need login before anyone else uses it?
5. Should part payments (₹999 lock, ₹6,000 balance) ever be counted at face value instead of one
   full ₹6,999 sale per person? Today it follows the reference reports exactly.
