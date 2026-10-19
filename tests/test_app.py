from __future__ import annotations

import json
import re

import pytest

from app import create_app
from app.config import ConfigError


# --- Settings (no database needed) ---------------------------------------------

def test_production_requires_a_secret_key():
    with pytest.raises(ConfigError, match="SECRET_KEY"):
        create_app({"APP_ENV": "production", "DATABASE_URL": "postgresql:///x", "SECRET_KEY": ""})


def test_dev_sign_in_is_refused_outside_local():
    with pytest.raises(ConfigError, match="DEV_SIGN_IN"):
        create_app({"APP_ENV": "staging", "DATABASE_URL": "postgresql:///x",
                    "SECRET_KEY": "x" * 40, "DEV_SIGN_IN": True})


def test_unknown_environment_is_refused():
    with pytest.raises(ConfigError, match="APP_ENV"):
        create_app({"APP_ENV": "prod", "DATABASE_URL": "postgresql:///x"})


# --- Public class finder ----------------------------------------------------------

def test_health_check(client):
    res = client.get("/healthz")
    assert res.status_code == 200
    assert res.get_json()["status"] == "ok"


def test_home_lists_only_cities_on_the_new_system(client):
    html = client.get("/").get_data(as_text=True)
    assert 'href="/richmond-va/"' in html
    assert 'href="/houston-tx/"' not in html          # still on Enrollware
    assert "Houston, TX" in html                       # listed as coming later


def test_city_on_enrollware_is_not_bookable(client):
    assert client.get("/houston-tx/").status_code == 404


def test_full_class_shows_waitlist_and_both_prices(client):
    html = client.get("/richmond-va/first-aid-cpr-aed/").get_data(as_text=True)
    assert "Join waitlist" in html
    assert "$108" in html and "$88" in html
    assert "3 of 12 seats left" in html                # Moorefield


def test_class_page_has_event_structured_data(client):
    html = client.get("/richmond-va/first-aid-cpr-aed/2027-01-16-henrico/").get_data(as_text=True)
    data = json.loads(re.search(r'<script type="application/ld\+json">(.*?)</script>', html, re.S).group(1))
    assert data["@type"] == "Event"
    assert data["startDate"] == "2027-01-16T09:00:00-05:00"   # local class time, whatever the server zone
    assert {o["availability"] for o in data["offers"]} == {"https://schema.org/SoldOut"}
    assert sorted(o["price"] for o in data["offers"]) == ["108.00", "88.00"]


def test_public_pages_never_show_private_class_details(app, client):
    from sqlalchemy import text
    from app import db
    with app.app_context(), db.transaction() as conn:
        conn.execute(text("""
            INSERT INTO site_private_details (site_id, access_code, poc_name)
            SELECT id, 'DOOR-4821', 'Pat Contact' FROM sites WHERE slug = 'henrico'
            ON CONFLICT (site_id) DO UPDATE SET access_code = 'DOOR-4821', poc_name = 'Pat Contact'
        """))
    try:
        for path in ["/", "/richmond-va/", "/richmond-va/first-aid-cpr-aed/",
                     "/richmond-va/first-aid-cpr-aed/2027-01-16-henrico/"]:
            html = client.get(path).get_data(as_text=True)
            assert "DOOR-4821" not in html and "Pat Contact" not in html, path
    finally:
        with app.app_context(), db.transaction() as conn:
            conn.execute(text("DELETE FROM site_private_details"))


# --- Staff dashboards and roles ---------------------------------------------------

def test_staff_pages_require_sign_in(client):
    res = client.get("/admin/d/customer_service")
    assert res.status_code == 302 and "/admin/sign-in" in res.headers["Location"]


def test_each_role_opens_its_own_dashboard(client, sign_in_as):
    sign_in_as("cs@example.test")
    html = client.get("/admin/d/customer_service").get_data(as_text=True)
    assert "Customer service dashboard" in html
    assert "Upcoming classes" in html
    assert "Classes that need an instructor" not in html   # coverage is not a CS permission


def test_a_role_you_do_not_hold_is_forbidden(client, sign_in_as):
    sign_in_as("cs@example.test")
    assert client.get("/admin/d/manager").status_code == 403


def test_operations_sees_coverage(client, sign_in_as):
    sign_in_as("ops@example.test")
    html = client.get("/admin/d/operations").get_data(as_text=True)
    assert "Classes that need an instructor" in html
    assert "Our Lady of Lourdes" in html


def test_two_role_account_can_switch(client, sign_in_as):
    sign_in_as("opslead@example.test")
    html = client.get("/admin/d/manager").get_data(as_text=True)
    assert 'href="/admin/d/operations"' in html
    assert client.get("/admin/d/operations").status_code == 200


def test_instructor_sees_lead_and_helper_jobs(client, sign_in_as):
    sign_in_as("marcus.hale@example.test")
    html = client.get("/portal/").get_data(as_text=True)
    assert "Helper" in html and "with Priya Raman" in html


def test_instructor_cannot_open_staff_dashboards(client, sign_in_as):
    sign_in_as("dana.whitfield@example.test")
    assert client.get("/admin/d/customer_service").status_code == 403


def test_webhooks_are_stubbed(client):
    assert client.post("/webhooks/stripe").status_code == 501
    assert client.post("/webhooks/ghl").status_code == 501
