#!/usr/bin/env bash
# Checks that running the migrations gives exactly the database that
# db/schema.sql + db/seed.sql describe, and that a full downgrade leaves
# nothing behind and upgrades cleanly again.
#
#   DATABASE_URL=postgresql:///postgres db/tests/migrations_match.sh
#
# Creates and drops two scratch databases on DATABASE_URL's server.
set -euo pipefail

ADMIN_URL="${DATABASE_URL:?set DATABASE_URL}"
HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$HERE/../.." && pwd)"
FLASK="${FLASK:-flask}"
REF="nbc_ref_$$"; MIG="nbc_mig_$$"
base="${ADMIN_URL%/*}"; query=""
if [[ "$ADMIN_URL" == *\?* ]]; then query="?${ADMIN_URL#*\?}"; base="${ADMIN_URL%%\?*}"; base="${base%/*}"; fi
REF_URL="$base/$REF$query"; MIG_URL="$base/$MIG$query"
TMP="$(mktemp -d)"

psql "$ADMIN_URL" -qc "CREATE DATABASE $REF" -c "CREATE DATABASE $MIG"
trap 'psql "$ADMIN_URL" -qc "DROP DATABASE IF EXISTS $REF" -c "DROP DATABASE IF EXISTS $MIG" >/dev/null; rm -rf "$TMP"' EXIT

psql "$REF_URL" -q -v ON_ERROR_STOP=1 -f "$ROOT/db/schema.sql" -f "$ROOT/db/seed.sql"
(cd "$ROOT" && APP_ENV=local DATABASE_URL="$MIG_URL" $FLASK --app wsgi db upgrade >/dev/null)

structure() { pg_dump "$1" --schema-only --no-owner --no-privileges -T alembic_version | grep -v '^--' | sed '/^\\\(un\)\?restrict/d' | grep -v '^$'; }
data() {
  psql "$1" -qtA -v ON_ERROR_STOP=1 <<'SQL'
SELECT 'setting ' || key || ' ' || value::text || ' ' || description FROM app_settings ORDER BY key;
SELECT 'family ' || row(code, name, slug, one_instructor_max, min_students_to_run)::text FROM course_families ORDER BY code;
SELECT 'role ' || row(code, name, dashboard_key, sign_in_method, is_staff, is_self_service, grants_all, is_scopable, sort_order)::text FROM roles ORDER BY code;
SELECT 'perm ' || row(code, area, description, own_records_only)::text FROM permissions ORDER BY code;
SELECT 'grant ' || role_code || ' ' || permission_code FROM role_permissions ORDER BY 1;
SQL
}

structure "$REF_URL" > "$TMP/ref.schema"; structure "$MIG_URL" > "$TMP/mig.schema"
data "$REF_URL" > "$TMP/ref.data";       data "$MIG_URL" > "$TMP/mig.data"
diff -u "$TMP/ref.schema" "$TMP/mig.schema" && echo "PASS  migrated structure matches db/schema.sql ($(grep -c '^CREATE TABLE' "$TMP/mig.schema") tables)"
diff -u "$TMP/ref.data" "$TMP/mig.data" && echo "PASS  migrated reference data matches db/seed.sql ($(wc -l < "$TMP/mig.data") rows compared)"

(cd "$ROOT" && APP_ENV=local DATABASE_URL="$MIG_URL" $FLASK --app wsgi db downgrade base --yes >/dev/null)
left=$(psql "$MIG_URL" -qtAc "SELECT count(*) FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
                               WHERE n.nspname = 'public' AND c.relkind IN ('r','v') AND c.relname <> 'alembic_version'")
fns=$(psql "$MIG_URL" -qtAc "SELECT count(*) FROM pg_proc p JOIN pg_namespace n ON n.oid = p.pronamespace
                              LEFT JOIN pg_depend d ON d.objid = p.oid AND d.deptype = 'e'
                              WHERE n.nspname = 'public' AND d.objid IS NULL")
[ "$left" = 0 ] && [ "$fns" = 0 ] && echo "PASS  full downgrade removes every table, view and function"
(cd "$ROOT" && APP_ENV=local DATABASE_URL="$MIG_URL" $FLASK --app wsgi db upgrade >/dev/null)
structure "$MIG_URL" > "$TMP/mig2.schema"
diff -q "$TMP/ref.schema" "$TMP/mig2.schema" >/dev/null && echo "PASS  upgrade after a full downgrade gives the same database"
