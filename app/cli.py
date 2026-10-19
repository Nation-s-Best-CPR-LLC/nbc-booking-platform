"""`flask db ...` commands: run database migrations from a shell (e.g. Replit's).

    flask --app wsgi db upgrade          # create or update the database to the latest version
    flask --app wsgi db current          # which version the database is on
    flask --app wsgi db history          # list every migration
    flask --app wsgi db downgrade -1     # undo the last migration (asks first)
    flask --app wsgi db new "add x"      # start a new migration file
    flask --app wsgi db load-demo        # invented demo data, local development only
"""

from __future__ import annotations

from pathlib import Path

import click
from alembic import command
from alembic.config import Config as AlembicConfig
from flask import Flask, current_app
from flask.cli import AppGroup

ROOT = Path(__file__).resolve().parent.parent
db_cli = AppGroup("db", help="Database migrations.")


def _alembic() -> AlembicConfig:
    cfg = AlembicConfig(str(ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(ROOT / "migrations"))
    cfg.attributes["database_url"] = current_app.config["DATABASE_URL"]
    return cfg


@db_cli.command("upgrade")
@click.argument("revision", default="head")
def upgrade(revision: str) -> None:
    """Bring the database up to REVISION (default: the latest)."""
    click.echo(f"Upgrading the {current_app.config['APP_ENV']} database to {revision} ...")
    command.upgrade(_alembic(), revision)
    click.echo("Done.")


@db_cli.command("downgrade", context_settings={"ignore_unknown_options": True})
@click.argument("revision")
@click.option("--yes", is_flag=True, help="Don't ask for confirmation.")
def downgrade(revision: str, yes: bool) -> None:
    """Undo migrations back to REVISION ('-1' for the last one, 'base' for all)."""
    env = current_app.config["APP_ENV"]
    if not yes:
        click.confirm(f"This removes database objects and their data on the {env} database. Continue?",
                      abort=True)
    if env == "production" and revision == "base":
        click.confirm("That deletes the whole production database. Type y only if you are sure.", abort=True)
    command.downgrade(_alembic(), revision)
    click.echo("Done.")


@db_cli.command("current")
def current() -> None:
    """Show which migration the database is on."""
    command.current(_alembic(), verbose=False)


@db_cli.command("history")
def history() -> None:
    """List every migration, oldest last."""
    command.history(_alembic(), verbose=False)


@db_cli.command("new")
@click.argument("message")
def new(message: str) -> None:
    """Start a new, empty migration file named after MESSAGE."""
    cfg = _alembic()
    from alembic.script import ScriptDirectory
    heads = ScriptDirectory.from_config(cfg).get_heads()
    next_id = f"{int(heads[0]) + 1:04d}" if heads and heads[0].isdigit() else None
    command.revision(cfg, message=message, rev_id=next_id)


@db_cli.command("load-demo")
def load_demo() -> None:
    """Load invented demo classes and accounts (password: demo-password). Local only."""
    if current_app.config["APP_ENV"] != "local":
        raise click.ClickException("Demo data is for local development only. APP_ENV is "
                                   f"{current_app.config['APP_ENV']!r}; refusing.")
    from . import db
    sql = (ROOT / "db" / "demo.sql").read_text()
    with db.engine().begin() as conn:
        if conn.exec_driver_sql("SELECT count(*) FROM metros").scalar():
            raise click.ClickException("This database already has city data. Load the demo into an empty one.")
        with conn.connection.dbapi_connection.cursor() as cur:
            cur.execute(sql)
    click.echo("Demo data loaded. Demo accounts sign in with: demo-password")


def init_app(app: Flask) -> None:
    app.cli.add_command(db_cli)
