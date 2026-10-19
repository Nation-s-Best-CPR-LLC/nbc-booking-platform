#!/usr/bin/env bash
# Last-seat race: N buyers on N separate connections try to hold the final
# seats of one class at the same moment, WITHOUT the app's own row lock (the
# worst case). Exactly SEATS of them must succeed.
#
#   DATABASE_URL=postgres://... db/tests/last_seat_race.sh [buyers] [seats]
#
# Creates and drops its own scratch database next to $DATABASE_URL's server.
set -euo pipefail

BUYERS="${1:-20}"
SEATS="${2:-1}"
ADMIN_URL="${DATABASE_URL:?set DATABASE_URL}"
HERE="$(cd "$(dirname "$0")" && pwd)"
DB="nbc_race_$$"
RACE_URL="${ADMIN_URL%/*}/$DB"

psql "$ADMIN_URL" -qc "CREATE DATABASE $DB"
trap 'psql "$ADMIN_URL" -qc "DROP DATABASE IF EXISTS $DB" >/dev/null' EXIT

psql "$RACE_URL" -q -v ON_ERROR_STOP=1 -f "$HERE/../schema.sql"
psql "$RACE_URL" -q -v ON_ERROR_STOP=1 -f "$HERE/../seed.sql"
psql "$RACE_URL" -q -v ON_ERROR_STOP=1 <<SQL
INSERT INTO metros (slug, name, state_code, market_code, time_zone, booking_system, cutover_at)
VALUES ('richmond-va', 'Richmond', 'VA', 'RVA', 'America/New_York', 'engine', now());
INSERT INTO sites (metro_id, slug, name, address_line1, city, state_code, postal_code, time_zone)
SELECT id, 'henrico', 'Henrico', '8100 Three Chopt Rd', 'Richmond', 'VA', '23229', 'America/New_York' FROM metros;
INSERT INTO rooms (site_id, max_student_count) SELECT id, 12 FROM sites;
INSERT INTO products (course_family_id, code, name, short_name, delivery_mode, ghl_course_code, base_price_cents)
SELECT id, 'AP_BL', 'A&P', 'A&P', 'blended', 'AP', 10800 FROM course_families WHERE code = 'FA_CPR_AED';
INSERT INTO sessions (metro_id, site_id, room_id, course_family_id, delivery_mode, starts_at, ends_at, time_zone, slug,
                      is_published, one_instructor_max, room_max_student_count, capacity)
SELECT m.id, s.id, r.id, cf.id, 'blended', now() + interval '30 days', now() + interval '30 days 4 hours',
       'America/New_York', 'race', true, 12, 12, $SEATS
FROM metros m, sites s, rooms r, course_families cf WHERE cf.code = 'FA_CPR_AED';
INSERT INTO session_products (session_id, product_id, course_family_id, delivery_mode, price_cents)
SELECT s.id, p.id, p.course_family_id, p.delivery_mode, 10800 FROM sessions s, products p;
SQL

buy() {
  psql "$RACE_URL" -qtA -v ON_ERROR_STOP=1 >/dev/null 2>&1 <<SQL
BEGIN;
WITH o AS (
  INSERT INTO orders (channel, buyer_first_name, buyer_last_name, buyer_email, livemode)
  VALUES ('web', 'Buyer', '$1', 'buyer$1@example.test', false) RETURNING id)
INSERT INTO seat_holds (session_id, order_id, kind, quantity, expires_at)
SELECT (SELECT id FROM sessions), id, 'checkout', 1, now() + interval '15 minutes' FROM o;
SELECT pg_sleep(0.2);   -- widen the window so commits really collide
COMMIT;
SQL
}

pids=()
for i in $(seq 1 "$BUYERS"); do buy "$i" & pids+=($!); done
ok=0; refused=0
for p in "${pids[@]}"; do if wait "$p"; then ok=$((ok+1)); else refused=$((refused+1)); fi; done

held=$(psql "$RACE_URL" -qtAc "SELECT held_seats FROM session_availability")
echo "buyers=$BUYERS seats=$SEATS succeeded=$ok refused=$refused seats_held_in_db=$held"
if [ "$ok" -eq "$SEATS" ] && [ "$held" -eq "$SEATS" ]; then
  echo "PASS  last-seat race: exactly $SEATS of $BUYERS concurrent buyers got a seat"
else
  echo "FAIL  last-seat race"; exit 1
fi
