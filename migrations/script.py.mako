"""${message}

Revision ID: ${up_revision}
Revises: ${down_revision | comma,n}
Created: ${create_date}

How to write this migration:
  * Plain SQL, run with run_sql(). Keep every statement safe to run once.
  * Also update db/schema.sql (and db/seed.sql for reference data) so it
    matches, and add a check to db/tests/schema_checks.sql.
  * Write a real downgrade, or raise NotImplementedError with the reason.
"""

from migrations.sqlfile import run_sql

revision = ${repr(up_revision)}
down_revision = ${repr(down_revision)}
branch_labels = ${repr(branch_labels)}
depends_on = ${repr(depends_on)}


def upgrade() -> None:
    run_sql("""
    -- SQL here
    """)


def downgrade() -> None:
    run_sql("""
    -- SQL that undoes upgrade()
    """)
