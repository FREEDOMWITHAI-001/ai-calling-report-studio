# Database schema — CoachEasily Report Studio

PostgreSQL (connection details in `backend/.env`), schema **`ai_report`** (never `public` — it holds
217 tables from other projects). Defined in `backend/app/models.py`. Row counts as of
2026-08-16.

## Table map

| Table | Rows | Purpose |
|---|---|---|
| `clients` | 1 | Tenant root. Everything hangs off `client_id`. |
| `events` | 0 | Webinar/session instances (client + name + date). Unused so far. |
| `bots` | 18 | AI calling bots; `role` = `signup` \| `day_of` \| `other`. |
| `persons` | 21,319 | Deduplicated identity. The join spine for all fact tables. |
| `registrations` | 12,856 | Webinar sign-ups + UTM attribution. |
| `ai_calls` | 41,810 | Every AI call: status, duration, outcome, transcript. |
| `sales` | 549 | Payments (full / lock / balance) with amount + product. |
| `attendance` | 15,738 | Who attended, and minutes in session. |
| `webinar_daily` | 999 | Pre-aggregated daily funnel from the client's own sheet. |
| `generic_datasets` / `generic_records` | 0 / 0 | Catch-all for uploads that match no known type. |
| `raw_uploads` | 6 | One row per uploaded file: mapping, counts, status. |
| `mapping_templates` | 0 | Remembered column mappings, keyed by header signature. |
| `methodology_configs` | 0 | Per-report overrides of `DEFAULT_METHODOLOGY`. |
| `report_runs` | 3 | Each generated report: window, filters, metrics JSON, output files. |

Empty tables are wired up but not yet exercised by the reference load.

## Core columns

### `persons` — identity resolution
`id`, `client_id`, `phone_norm`, `email_norm`, `name_norm`, `display_name`, `email`,
`phone`, `is_team`

Matching precedence is **phone → email → name**, and `name_norm` is only trusted when the
row has no usable phone. `is_team` flags internal/test people so they can be excluded from
metrics.

### `registrations`
`person_id`, `event_id`, `upload_id`, `name`, `email`, `phone`, `phone_norm`,
`registered_at`, `registration_date`, `language`, `program`,
`utm_source`, `utm_medium`, `utm_campaign`, `utm_content`, `utm_adname`,
`salary_band`, `gender`, `row_hash`, `raw` (JSON)

### `ai_calls`
`person_id`, `bot_id`, `bot_name`, `upload_id`, `contact_name`, `phone`, `phone_norm`,
`email`, `status`, `outcome`, `goal_outcome`, `interest_level`, `sentiment`,
`lead_temperature`, `duration_s`, `turns`, `red_flags`, `summary`, `transcript`,
`recording_url`, `call_sid`, `started_at`, `ended_at`, `source_created_at`, `call_date`,
`row_hash`, `raw`

`duration_s` × cost-per-minute drives talk cost; `duration_s` vs the connect threshold in
`DEFAULT_METHODOLOGY` decides "connected".

### `sales`
`person_id`, `upload_id`, `name`, `email`, `phone`, `phone_norm`, `amount`, `sold_at`,
`sale_date`, `product`, `payment_type` (full/lock/balance), `payment_id`,
`payment_status`, `language`, `row_hash`, `raw`

### `attendance`
`person_id`, `event_id`, `upload_id`, `name`, `email`, `phone`, `phone_norm`,
`attended_on`, `minutes_in_session`, `language`, `row_hash`, `raw`

This export carries "Not Found" phone numbers and platform alias emails, which is why name
matching must stay enabled for it.

### `webinar_daily`
`day`, `language`, `leads`, `show_up`, `attendees_at_pitch`, `total_sale`, `total_lock`,
`row_hash`, `raw`

### `raw_uploads` (audit / idempotency)
`filename`, `stored_path`, `content_type`, `size_bytes`, `sheet_name`, `dataset_type`,
`generic_dataset_name`, `client_id`, `mapping` (JSON), `options` (JSON), `row_count`,
`inserted_count`, `skipped_count`, `status`, `error_detail`, `uploaded_by`, `uploaded_at`,
`finished_at`

### `report_runs`
`title`, `client_id`, `methodology_id`, `date_from`, `date_to`, `filters`, `formats`,
`status`, `error_detail`, `metrics` (JSON), `files` (JSON), `generated_by`, `generated_at`,
`finished_at`

## Cross-cutting conventions

- **`row_hash`** (MD5 of row content) on every fact table makes ingestion idempotent —
  re-uploading a file inserts nothing, but a genuine repeat registration still lands.
- **`raw`** JSON keeps the original row so nothing is lost to column mapping.
- **`upload_id`** traces every fact row back to the file it came from.
- **`created_at` / `updated_at`** via `TimestampMixin` on most tables.
- Extra indexes: `ix_calls_bot_date` (`bot_name`, `call_date`),
  `ix_reg_client_date` (`client_id`, `registration_date`).
- Dropping `DATABASE_URL` from `backend/.env` falls back to SQLite at `backend/data/app.db`
  with the same schema.
