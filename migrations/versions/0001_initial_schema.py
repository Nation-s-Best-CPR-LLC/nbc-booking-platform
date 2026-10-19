"""Initial schema: every table, view, function and rule of the booking engine.

Revision ID: 0001
Revises:
Created: 2026-10-19

The SQL is migrations/sql/0001_initial_schema.sql, a frozen copy of
db/schema.sql at this point. Needs the citext, pg_trgm and btree_gist
extensions (available on Replit PostgreSQL / Neon and standard PostgreSQL 16).
"""

from migrations.sqlfile import run_sql, run_sql_file

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    run_sql_file("0001_initial_schema.sql")


def downgrade() -> None:
    # Removes everything 0001 created. Extensions are left installed (other
    # databases' objects may use them); drop them by hand if wanted.
    run_sql("""
        DROP VIEW IF EXISTS
        session_availability, session_break_even, sessions_needing_instructor,
        unsynced_items, user_effective_permissions, waitlist_queue
        CASCADE;
        DROP TABLE IF EXISTS
        action_tokens, airtable_records, app_settings, assignments, attendance_marks,
        audit_log, auth_sessions, availability_blocks, cert_type_course_families,
        checkout_sessions, class_offer_requests, class_offers, consent_records,
        course_families, external_seat_reservations, ghl_stage_map, instructor_certs,
        instructor_equipment, instructors, integration_issues, integration_runs, metros,
        notes, notifications, oauth_connections, order_attribution, orders, outbox_jobs,
        page_content, pay_records, payments, people, permissions, policy_versions,
        products, rate_card, refunds, registration_transfers, registrations,
        role_permissions, roles, room_course_families, rooms, seat_holds,
        seat_overrides, session_airtable_records, session_private_details,
        session_products, sessions, site_private_details, sites, time_off,
        url_redirects, user_accounts, user_identities, user_roles, waitlist_entries,
        waitlist_offers, webhook_events
        CASCADE;
        DROP FUNCTION IF EXISTS
        set_updated_at(), is_seat_consuming(text),
        user_has_permission(bigint,text,bigint), audit_log_immutable(),
        session_seats_used(bigint), session_seat_limit(bigint),
        session_seats_available(bigint), assert_session_capacity(bigint),
        trg_capacity_from_session_id(), trg_capacity_from_sessions(),
        trg_hold_requires_live_session(), trg_waitlist_limit(), trg_room_hosts_family(),
        trg_require_permission(), trg_co_instructor_room_check(),
        trg_assignment_range_default(), trg_session_time_to_assignments(),
        trg_session_cancel_releases_instructors(), grant_student_role_if_booked(bigint),
        trg_registration_grants_student()
        CASCADE;
    """)
