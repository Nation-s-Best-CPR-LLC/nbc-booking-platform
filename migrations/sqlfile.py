"""Helpers for SQL-based migrations.

Migrations are plain SQL because the app uses plain SQL (no ORM models), so
there is nothing for Alembic to autogenerate from. Large migrations keep their
SQL in migrations/sql/<revision>.sql, frozen at the time they were written:
later edits to db/schema.sql never change what an old migration does.
"""

from __future__ import annotations

from pathlib import Path

from alembic import op

SQL_DIR = Path(__file__).resolve().parent / "sql"


def run_sql(sql: str) -> None:
    """Run one or more SQL statements inside the migration's transaction."""
    conn = op.get_bind()
    raw = conn.connection.dbapi_connection          # psycopg connection
    with raw.cursor() as cur:
        cur.execute(sql)                            # no parameters: several statements allowed


def run_sql_file(name: str) -> None:
    run_sql((SQL_DIR / name).read_text())
