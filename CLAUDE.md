# Conventions for this repo

NBC booking engine: Flask + PostgreSQL on Replit. Read `docs/source-of-truth.md`
and `docs/database-architecture.md` before changing data or integrations.

## Data
- One system of record per piece of data. Airtable owns the schedule,
  locations, courses and prices; this engine owns seats, holds, registrations,
  waitlists, transfers, refunds, roles and the instructor portal; Stripe owns
  cards and money movement; GHL owns contact details and conversations. Don't
  add a column that copies another platform's data without updating
  `docs/source-of-truth.md` with the reason.
- The database enforces the business rules (no overselling, permissions on
  extra seats and large refunds, Enrollware/engine per city). Don't
  re-implement them only in Python; let the database refuse and handle the error.
- Writes go through `db.transaction()`. Lock a class row with
  `FOR NO KEY UPDATE`, never `FOR UPDATE` (it deadlocks against foreign keys).
- Money is integer cents. Times are timestamptz; show class times in the
  class's own time zone (`filters.local_dt`).
- Schema changes: edit `db/schema.sql` (until Alembic is added), add a check to
  `db/tests/schema_checks.sql`, update the docs in the same PR.

## Security and privacy
- Public pages never select from `*_private_details` (access codes, on-site
  contacts) and never show payment details.
- Check permissions with `auth.permission_required(...)` or
  `current_user().can(permission, metro_id)`. Roles and permissions are data
  (`db/seed.sql`), not hard-coded role names.
- Secrets come from environment variables only. Never commit keys; `.env` is ignored.
- `DEV_SIGN_IN` and `db/demo.sql` are for local development only.

## Copy
- Customer- and staff-facing text is plain English: "helper instructor", not
  "co-instructor" in the UI; "city", not "metro"; no tool names (GHL, Airtable)
  on customer pages.

## Checks before a PR
`pytest` (with `TEST_DATABASE_URL`), `db/tests/schema_checks.sql`, and
`scripts/export_preview.py` still runs.
