"""Instructor portal at /portal (phase 4c).

Same "instructor" role whether someone leads a class or helps in it; the job
in each class comes from assignments.role. Instructors only ever see their
own classes.
"""

from __future__ import annotations

from flask import Blueprint, abort, render_template

from .. import auth, db

bp = Blueprint("portal", __name__, url_prefix="/portal")


@bp.get("/")
@auth.permission_required("own.classes_view")
def index():
    user = auth.current_user()
    instructor = db.fetch_one("""
        SELECT id, first_name, last_name, home_metro_id FROM instructors WHERE user_account_id = :uid
    """, uid=user.id)
    if instructor is None:
        abort(403)
    classes = db.fetch_all("""
        SELECT s.id, s.starts_at, s.ends_at, s.time_zone, asg.role AS my_role,
               si.name AS site_name, si.city, cf.name AS course_name,
               a.sold_seats, a.seat_limit, a.seats_left, a.waitlist_count,
               (SELECT i2.first_name || ' ' || i2.last_name FROM assignments o
                  JOIN instructors i2 ON i2.id = o.instructor_id
                 WHERE o.session_id = s.id AND o.status = 'assigned' AND o.instructor_id <> asg.instructor_id
                 LIMIT 1) AS teaching_with
          FROM assignments asg
          JOIN sessions s ON s.id = asg.session_id
          JOIN sites si ON si.id = s.site_id
          JOIN course_families cf ON cf.id = s.course_family_id
          JOIN session_availability a ON a.session_id = s.id
         WHERE asg.instructor_id = :iid AND asg.status = 'assigned' AND s.starts_at > now()
         ORDER BY s.starts_at
    """, iid=instructor["id"])
    open_offers = db.fetch_all("""
        SELECT o.id, o.role, o.rate_cents, o.priority_until, s.starts_at, s.ends_at, s.time_zone,
               si.name AS site_name, cf.name AS course_name
          FROM class_offers o
          JOIN sessions s ON s.id = o.session_id
          JOIN sites si ON si.id = s.site_id
          JOIN course_families cf ON cf.id = s.course_family_id
         WHERE o.status = 'open' AND s.starts_at > now()
         ORDER BY s.starts_at
    """)
    certs = db.fetch_all("""
        SELECT cert_type, expires_on FROM instructor_certs WHERE instructor_id = :iid ORDER BY expires_on
    """, iid=instructor["id"])
    return render_template("portal/index.html", instructor=instructor, classes=classes,
                           open_offers=open_offers, certs=certs)
