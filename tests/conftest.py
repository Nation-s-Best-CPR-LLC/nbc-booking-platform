"""Test setup.

App tests need a database loaded with db/schema.sql, db/seed.sql and
db/demo.sql. Point TEST_DATABASE_URL at it:

    createdb nbc_test
    psql nbc_test -f db/schema.sql -f db/seed.sql -f db/demo.sql
    TEST_DATABASE_URL=postgresql:///nbc_test pytest

Without TEST_DATABASE_URL the database tests are skipped.
"""

from __future__ import annotations

import os

import pytest

from app import create_app


@pytest.fixture(scope="session")
def database_url() -> str:
    url = os.environ.get("TEST_DATABASE_URL")
    if not url:
        pytest.skip("TEST_DATABASE_URL is not set")
    return url


@pytest.fixture()
def app(database_url):
    return create_app({"APP_ENV": "local", "DATABASE_URL": database_url, "DEV_SIGN_IN": True, "TESTING": True})


@pytest.fixture()
def client(app):
    return app.test_client()


@pytest.fixture()
def sign_in_as(client, app):
    """Sign the test client in as a demo account, by email."""
    from sqlalchemy import text

    def _sign_in(email: str) -> None:
        with app.app_context():
            from app import db
            uid = db.connection().execute(text("SELECT id FROM user_accounts WHERE email = :e"), {"e": email}).scalar_one()
        with client.session_transaction() as sess:
            sess["user_id"] = uid

    return _sign_in
