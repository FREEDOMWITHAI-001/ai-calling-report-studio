# Build Prompt: CoachEasily Report Generation Application

## Role
You are a **world-class report design expert and UI/UX engineer**. You have deep
experience building internal analytics/reporting tools that business teams actually
enjoy using — clean data ingestion, trustworthy calculations, and polished,
presentation-ready output (PDF/Excel/PPT). Apply that judgment throughout: where this
prompt is ambiguous, make the decision a senior product engineer would make, note the
assumption you made, and keep moving rather than blocking on it.

## What to Build
A full-stack web application that:
1. Lets a user **upload data files of various types** (registration data, AI calling
   data, sales data, and potentially other data types not yet specified — the upload
   system should be **general-purpose and flexible**, not hardcoded to only 2–3 fixed
   schemas).
2. Stores the uploaded data in a relational database, normalized appropriately per
   data type.
3. Generates polished, presentation-ready reports over a **user-selected date range**,
   output as **PDF, Excel, and/or PowerPoint**, styled and structured to match the
   sample reports referenced below.
4. Results in a **working, runnable application** — not just scaffolding or a partial
   prototype. At the end of the build, the user should be able to run one or two
   commands locally and have the app up and usable in a browser.

## Reference Reports (source of truth for report structure & metrics)
These are real report outputs from the business this app is being built for. Use them
as the template for section structure, metric definitions, and styling. **Fetch and
read these directly** (they're view-only Google Sheets) — do not guess their contents:

- Sample report 1 (26 Jun – 17 Jul 2026 window):
  https://docs.google.com/spreadsheets/d/1Ny9IZ3dSUub_yWGKQTeAKX_ZOIiz1i9l/edit?gid=2074210124#gid=2074210124
- Sample report 2 (17 Jul – 14 Aug 2026 window):
  https://docs.google.com/spreadsheets/d/1W3gjHFt32wYdsR5Mappk32hEIA8WDTci/edit?usp=sharing&ouid=104615665172368860406&rtpof=true&sd=true
- Raw underlying data (Google Drive folder):
  https://drive.google.com/drive/folders/1RB8jcLU7HQpa8FD8q05mDOBxHB7C9BBX?usp=sharing

**Known structure from these reports** (confirm/expand once you can read the full
sheets, including the second tab in each file called "CBA X report," which holds
per-bot, per-day detail not visible on the default tab):
- Title: "COACHEASILY — WHAT AI CALLING ADDED (CBA X · English)"
- Subtitle line: date range, workshop segment, and base-population definition
  (e.g. "base = registrants," "connected = talk > 15s").
- Core table — **"Revenue With AI Calling vs Without"**:
  | Program | Revenue without AI | Revenue with AI | AI added | Relative uplift | ROI |
- A methodology footnote explaining exactly how "with AI," "without AI," and "ROI"
  are calculated (buyer counts, connect-rate lift, talk-cost basis) — this
  methodology must be **configurable/traceable in the data model**, not hardcoded
  as static text, since it references live counts (registrant base, connected
  leads, buy-lift percentage, talk cost).
- A second tab per report with per-bot, per-day granular detail — the report
  generator should be able to reproduce this level of detail from the underlying
  data, not just the summary table.

⚠️ **Access note:** These Drive links are view-only and the raw data folder listing
could not be fully retrieved via automated fetch. Before finalizing the database
schema, use the file-upload feature of the app itself (or ask the user directly) to
get real sample files rather than reverse-engineering the schema purely from the
summary tab.

## Tech Stack
- **Backend:** Python — FastAPI (preferred: async, clean API layer, good fit for
  background report-generation jobs) or Django if built-in admin/auth is preferred.
- **Frontend:** React, with a clean component library (MUI or shadcn/ui) — this is a
  UI-forward tool, invest real effort in a dashboard that feels professional, not a
  bare CRUD scaffold.
- **Database:** PostgreSQL.
- **Background jobs:** Celery + Redis, or framework-native background tasks for a
  simpler v1 — report generation and large file ingestion should never block the
  request thread.
- **File storage:** Local disk (fine for v1) or S3-compatible bucket for uploaded raw
  files and generated report outputs.

## Data Upload — Must Be General-Purpose
Do not hardcode the upload flow to only accept 2–3 fixed file types. Instead:
- Support CSV/XLSX upload for **any data type** the user throws at it.
- On upload, show a **preview + column-mapping step** so the user can tell the system
  what each column represents and which existing table (or new table) it belongs to.
- Maintain a `raw_uploads` log table: filename, source/data type, uploaded_by,
  uploaded_at, row_count, status (success/partial/failed), error detail.
- Known data types to design first-class support for, based on prior discussion:
  1. **Registration data** — username, phone, email.
  2. **AI calling data** — call logs/outcomes (exact fields to be confirmed against
     the real raw data in the Drive folder above — likely includes bot ID, call
     timestamp, duration, connected/not-connected status, outcome).
  3. **Sales data** — transaction/conversion records tied back to registrations.
- Use a common linking key across tables (phone number is the most likely candidate
  based on the reference reports) so reports can join registration → calling → sales
  per contact. Validate and de-duplicate on this key during upload.
- Add `created_at`/`updated_at` timestamps on all tables for auditability.

## Report Generation
- User selects a **date range** (custom start/end, plus presets like "Last 7 days,"
  "This month").
- User selects **output format(s)**: PDF, Excel, PowerPoint — support generating
  **multiple formats in a single action**, and/or multiple date ranges at once
  (batch generation).
- Backend computes the metrics shown in the reference reports (revenue with/without
  AI, AI added, relative uplift, ROI) plus per-bot/per-day detail, for the selected
  range, and renders into the chosen format(s) matching the reference styling.
- **PDF:** clean, print-ready, matches reference report layout and branding.
- **Excel:** summary tab + underlying detail tabs (mirroring the "Overview" +
  "CBA X report" tab structure from the reference sheets).
- **PowerPoint:** dashboard-style — KPIs and charts per slide, suitable for sharing
  with stakeholders.
- Store every generated report with metadata (date range, format, generated_at,
  generated_by) so past reports can be re-downloaded without regenerating.

## Deliverables for This Build Session
1. A working application (backend + frontend + database migrations) that runs
   locally with a minimal setup — ideally one or two commands (e.g.
   `docker-compose up`, or a documented `setup.sh` + `run.sh`).
2. A README with exact run instructions, and what URL/port to open in the browser.
3. Seed/sample data or a way to quickly test upload → report generation end-to-end
   even before the real raw data files are available.
4. Clear TODO/open-questions list for anything you had to assume due to not having
   direct access to the full raw data (see open questions below) — flag these
   rather than silently guessing on anything that affects calculation accuracy.

## Open Questions to Confirm Before/While Building
1. Exact field structure of the AI calling data (call duration, outcome/status,
   bot/agent ID, timestamp, transcript link, etc.) — check the raw data folder or
   ask the user to upload a real sample file early.
2. Confirm the join key across registration/calling/sales data (phone number is the
   leading candidate).
3. Authentication/user-role requirements — is this single-user internally, or does
   it need login/roles?
4. Expected data volume per upload — affects whether synchronous processing is
   acceptable or background jobs are required from day one.
5. Retention policy — should generated reports and raw uploads be kept indefinitely
   or cleaned up after some period?

## Important
Treat the two reference report links above as the ground truth for what a "correct"
report looks like. If anything in this prompt conflicts with what those reports
actually show once you're able to read them in full (including the "CBA X report"
tab), the reference reports win — flag the conflict and adjust.



https://docs.google.com/spreadsheets/d/1W3gjHFt32wYdsR5Mappk32hEIA8WDTci/edit?usp=sharing&ouid=104615665172368860406&rtpof=true&sd=true

raw data
https://drive.google.com/drive/folders/1RB8jcLU7HQpa8FD8q05mDOBxHB7C9BBX?usp=sharing


Ask as many questions you want if you have?