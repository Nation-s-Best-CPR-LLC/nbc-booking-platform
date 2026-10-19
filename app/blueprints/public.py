"""Public class finder: city area → course → date and location → class.

Server-rendered so search engines can index every page. Only data safe for
the public is selected here: never access codes, on-site contacts or payment
details (those live in *_private_details tables, which this module never reads).
"""

from __future__ import annotations

from flask import Blueprint, abort, current_app, render_template, url_for

from .. import db
from ..filters import local_dt

bp = Blueprint("public", __name__)

_SELLABLE = """
  s.status = 'scheduled' AND s.is_published AND s.starts_at > now()
  AND m.booking_system = 'engine' AND m.is_active
"""


@bp.get("/")
def home():
    metros = db.fetch_all(f"""
        SELECT m.slug, m.name, m.state_code,
               count(s.id) AS upcoming,
               min(s.starts_at) AS next_starts_at,
               min(s.time_zone) AS time_zone
          FROM metros m
          LEFT JOIN sessions s ON s.metro_id = m.id AND s.status = 'scheduled' AND s.is_published AND s.starts_at > now()
         WHERE m.is_active AND m.booking_system = 'engine'
         GROUP BY m.id
         ORDER BY m.name
    """)
    coming = db.fetch_all("""
        SELECT name, state_code FROM metros
         WHERE is_active AND booking_system = 'enrollware' ORDER BY name
    """)
    return render_template("public/home.html", metros=metros, coming=coming)


def _metro_or_404(slug: str) -> dict:
    metro = db.fetch_one("""
        SELECT id, slug, name, state_code, time_zone FROM metros
         WHERE slug = :slug AND is_active AND booking_system = 'engine'
    """, slug=slug)
    if not metro:
        abort(404)
    return metro


@bp.get("/<metro_slug>/")
def metro(metro_slug: str):
    metro = _metro_or_404(metro_slug)
    courses = db.fetch_all(f"""
        SELECT cf.slug, cf.name, cf.code,
               count(s.id) AS upcoming,
               min(s.starts_at) AS next_starts_at,
               (SELECT min(sp.price_cents) FROM session_products sp
                  JOIN sessions s2 ON s2.id = sp.session_id
                 WHERE s2.metro_id = :mid AND s2.course_family_id = cf.id AND sp.is_offered) AS from_price_cents
          FROM course_families cf
          JOIN sessions s ON s.course_family_id = cf.id
          JOIN metros m ON m.id = s.metro_id
         WHERE s.metro_id = :mid AND {_SELLABLE}
         GROUP BY cf.id
         ORDER BY cf.id
    """, mid=metro["id"])
    sites = db.fetch_all("""
        SELECT name, address_line1, address_line2, city, state_code, postal_code
          FROM sites WHERE metro_id = :mid AND is_active ORDER BY name
    """, mid=metro["id"])
    return render_template("public/metro.html", metro=metro, courses=courses, sites=sites)


def _class_rows(where: str, **params) -> list[dict]:
    return db.fetch_all(f"""
        SELECT s.id, s.slug, s.starts_at, s.ends_at, s.time_zone, s.delivery_mode,
               si.name AS site_name, si.city,
               cf.slug AS course_slug, cf.name AS course_name,
               a.seats_left, a.seat_limit, a.waitlist_count,
               (SELECT json_agg(json_build_object('name', p.short_name, 'price', sp.price_cents)
                                ORDER BY sp.price_cents DESC)
                  FROM session_products sp JOIN products p ON p.id = sp.product_id
                 WHERE sp.session_id = s.id AND sp.is_offered) AS offers
          FROM sessions s
          JOIN metros m ON m.id = s.metro_id
          JOIN sites si ON si.id = s.site_id
          JOIN course_families cf ON cf.id = s.course_family_id
          JOIN session_availability a ON a.session_id = s.id
         WHERE {_SELLABLE} AND {where}
         ORDER BY s.starts_at, si.name
    """, **params)


@bp.get("/<metro_slug>/<course_slug>/")
def course(metro_slug: str, course_slug: str):
    metro = _metro_or_404(metro_slug)
    family = db.fetch_one("SELECT id, slug, name, code, one_instructor_max FROM course_families WHERE slug = :s",
                          s=course_slug)
    if not family:
        abort(404)
    classes = _class_rows("s.metro_id = :mid AND s.course_family_id = :fid", mid=metro["id"], fid=family["id"])
    return render_template("public/course.html", metro=metro, family=family, classes=classes)


@bp.get("/<metro_slug>/<course_slug>/<class_slug>/")
def class_detail(metro_slug: str, course_slug: str, class_slug: str):
    metro = _metro_or_404(metro_slug)
    rows = _class_rows("s.metro_id = :mid AND cf.slug = :cs AND s.slug = :ss",
                       mid=metro["id"], cs=course_slug, ss=class_slug)
    if not rows:
        abort(404)
    cls = rows[0]
    site = db.fetch_one("""
        SELECT si.name, si.address_line1, si.address_line2, si.city, si.state_code, si.postal_code,
               si.parking_notes_public, si.directions_public
          FROM sessions s JOIN sites si ON si.id = s.site_id WHERE s.id = :id
    """, id=cls["id"])
    canonical = current_app.config["PUBLIC_BASE_URL"].rstrip("/") + url_for(
        "public.class_detail", metro_slug=metro_slug, course_slug=course_slug, class_slug=class_slug)
    return render_template("public/class_detail.html", metro=metro, cls=cls, site=site,
                           canonical_url=canonical, event_ld=_event_ld(cls, site, canonical))


def _event_ld(cls: dict, site: dict, url: str) -> dict:
    """schema.org Event for one class (decision D4: class pages only)."""
    street = site["address_line1"] + (f", {site['address_line2']}" if site["address_line2"] else "")
    availability = "https://schema.org/InStock" if cls["seats_left"] > 0 else "https://schema.org/SoldOut"
    return {
        "@context": "https://schema.org",
        "@type": "Event",
        "name": f"{cls['course_name']} – {site['name']}",
        # Local class time with its UTC offset, e.g. 2027-01-16T09:00:00-05:00
        "startDate": local_dt(cls["starts_at"], cls["time_zone"]).isoformat(),
        "endDate": local_dt(cls["ends_at"], cls["time_zone"]).isoformat(),
        "eventStatus": "https://schema.org/EventScheduled",
        "location": {
            "@type": "Place",
            "name": site["name"],
            "address": {
                "@type": "PostalAddress", "streetAddress": street, "addressLocality": site["city"],
                "addressRegion": site["state_code"], "postalCode": site["postal_code"], "addressCountry": "US",
            },
        },
        "organizer": {"@type": "Organization", "name": "Nation's Best CPR", "url": "https://nationsbestcpr.com"},
        "offers": [
            {"@type": "Offer", "name": o["name"], "price": f"{o['price'] / 100:.2f}", "priceCurrency": "USD",
             "availability": availability, "url": url}
            for o in (cls["offers"] or [])
        ],
    }
