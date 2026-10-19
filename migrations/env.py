"""Alembic environment: connects with DATABASE_URL and runs each migration in
its own transaction (PostgreSQL rolls back a failed migration completely)."""

from __future__ import annotations

import os
import sys
from pathlib import Path

from alembic import context
from sqlalchemy import create_engine, pool

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.db import _normalise_url  # noqa: E402

config = context.config


def database_url() -> str:
    url = config.attributes.get("database_url") or os.environ.get("DATABASE_URL")
    if not url:
        raise SystemExit("DATABASE_URL is not set. On Replit, add a PostgreSQL database first; "
                         "it sets DATABASE_URL for you.")
    return _normalise_url(url)


def run_offline() -> None:
    """`alembic upgrade head --sql` prints the SQL instead of running it."""
    context.configure(url=database_url(), literal_binds=True, transaction_per_migration=True)
    with context.begin_transaction():
        context.run_migrations()


def run_online() -> None:
    connection = config.attributes.get("connection")
    if connection is not None:              # called from the Flask CLI with an open connection
        context.configure(connection=connection, transaction_per_migration=True)
        with context.begin_transaction():
            context.run_migrations()
        return
    engine = create_engine(database_url(), poolclass=pool.NullPool)
    with engine.connect() as conn:
        context.configure(connection=conn, transaction_per_migration=True)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_offline()
else:
    run_online()
