"""Reference data: course families, business settings, roles and permissions.

Revision ID: 0002
Revises: 0001
Created: 2026-10-19

The SQL is migrations/sql/0002_reference_data.sql, a frozen copy of
db/seed.sql at this point. It also records which environment this database
belongs to, from APP_ENV at the time you run it (local, staging or
production), so /healthz can catch a test app pointed at the live database.
Locations, rooms, products and classes are not loaded here: the Airtable
sync creates them.
"""

import json
import os

from alembic import op
from sqlalchemy import text

from migrations.sqlfile import run_sql, run_sql_file

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    run_sql_file("0002_reference_data.sql")
    env = os.environ.get("APP_ENV", "local")
    if env not in {"local", "staging", "production"}:
        raise SystemExit(f"APP_ENV must be local, staging or production, not {env!r}")
    op.get_bind().execute(
        text("UPDATE app_settings SET value = CAST(:v AS jsonb) WHERE key = 'environment'"),
        {"v": json.dumps(env)},
    )


def downgrade() -> None:
    run_sql("""
        DELETE FROM role_permissions;
        DELETE FROM user_roles;
        DELETE FROM permissions;
        DELETE FROM roles;
        DELETE FROM app_settings;
        DELETE FROM course_families;
    """)
