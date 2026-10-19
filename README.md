# NBC booking platform

Nation's Best CPR's own class booking engine. Classes are planned in Airtable,
sold here (classes.nationsbestcpr.com), paid through Stripe Checkout, and
followed up in GHL. The plan and dates live in the NBC Booking Launch Hub; this
repo holds the code and the technical docs.

## What's here

```
app/                 Flask app
  __init__.py        create_app(): settings, database, blueprints
  config.py          settings from environment variables
  db.py              one SQLAlchemy engine; plain SQL helpers; transaction()
  auth.py            current user, roles, permission checks (user_has_permission in the DB)
  blueprints/
    public.py        class finder: /, /<city>/, /<city>/<course>/, /<city>/<course>/<class>/
    admin.py         staff side: /admin sign-in and one dashboard per role (/admin/d/<role>)
    portal.py        instructor portal: /portal
    webhooks.py      /webhooks/stripe, /webhooks/ghl (stubs until phases 3 and 4)
    health.py        /healthz
  templates/, static/app.css
db/
  schema.sql         the database (59 tables): see docs/database-architecture.md
  seed.sql           course families, settings, roles and permissions
  demo.sql           invented Richmond classes and accounts (local only, never production)
  tests/             database rule checks and the last-seat race test
docs/                architecture, source of truth, data ownership
scripts/
  export_preview.py  render every page to static HTML for sharing
tests/               app tests (pytest)
wsgi.py              entry point for flask / gunicorn
```

## Run it locally

You need Python 3.12+ and PostgreSQL 16.

```bash
python -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt

createdb nbc
psql nbc -v ON_ERROR_STOP=1 -f db/schema.sql -f db/seed.sql -f db/demo.sql

cp .env.example .env           # set DATABASE_URL=postgresql:///nbc
flask --app wsgi run --debug   # http://localhost:5000
```

Staff pages: open `/admin/sign-in` and pick a demo account (development
sign-in, refused outside `APP_ENV=local`). Each account opens its role's
dashboard; "Demo Ops Lead" has two roles and can switch.

## Tests

```bash
createdb nbc_test
psql nbc_test -v ON_ERROR_STOP=1 -f db/schema.sql -f db/seed.sql -f db/demo.sql
TEST_DATABASE_URL=postgresql:///nbc_test pytest                    # app tests
psql nbc_test -v ON_ERROR_STOP=1 -f db/tests/schema_checks.sql     # database rules
DATABASE_URL=postgresql:///postgres db/tests/last_seat_race.sh 40 12
```

## Shareable preview

```bash
DATABASE_URL=postgresql:///nbc python scripts/export_preview.py   # writes build/preview/
```

Renders every page with the demo data into static HTML (links rewritten,
stylesheet inlined, server-only buttons switched off). `build/preview/index.html`
lists them all. `build/` is not committed.

## Deploy (Replit Reserved VM)

`.replit` runs gunicorn on port 5000. Set these as Replit Secrets:
`APP_ENV` (`staging` or `production`), `DATABASE_URL`, `SECRET_KEY` (32+
random characters), `PUBLIC_BASE_URL`. Load `db/schema.sql` and `db/seed.sql`
into the database, then set `app_settings.environment` to match `APP_ENV`
(`/healthz` reports a mismatch). Never load `db/demo.sql` there.

## Build phases

| Phase | Status |
|---|---|
| Database schema, roles and permissions | Done (PR #1) |
| App skeleton, class finder pages, role dashboards, instructor portal shell | This branch |
| 1. Airtable sync | Next |
| 2. Search pages and SEO | Pages started; sitemap, breadcrumbs, redirects to do |
| 3. Seat holds and Stripe Checkout | To do |
| 4. GHL sync · 4a tracking · 4b CS console + Microsoft sign-in · 4c instructor portal | To do |
