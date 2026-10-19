"""Staff side at /admin: sign-in and one dashboard per role.

Each role in the `roles` table has a dashboard. A person with several roles
switches between them. What a dashboard shows depends on the permissions the
role grants, so adding a permission to a role in the database adds its panel.
"""

from __future__ import annotations

from collections import OrderedDict

from flask import Blueprint, abort, redirect, render_template, request, url_for

from .. import auth, db

bp = Blueprint("admin", __name__, url_prefix="/admin")


@bp.get("/")
def index():
    user = auth.current_user()
    if user is None:
        return redirect(url_for("admin.sign_in_page"))
    staff_roles = [r for r in user.roles if r["code"] != "instructor"]
    if not staff_roles:
        return redirect(url_for("portal.index"))
    return redirect(url_for("admin.dashboard", role_code=staff_roles[0]["code"]))


@bp.get("/sign-in")
def sign_in_page():
    accounts = []
    if auth.dev_sign_in_enabled():
        accounts = db.fetch_all("""
            SELECT a.id, a.display_name, a.email,
                   string_agg(r.name, ', ' ORDER BY r.sort_order) AS role_names,
                   (array_agg(r.code ORDER BY r.sort_order))[1] AS first_role
              FROM user_accounts a
              JOIN user_roles ur ON ur.user_account_id = a.id AND ur.revoked_at IS NULL
              JOIN roles r ON r.code = ur.role_code
             WHERE a.status = 'active'
             GROUP BY a.id
             ORDER BY min(r.sort_order), a.display_name
        """)
    return render_template("admin/sign_in.html", accounts=accounts,
                           dev_enabled=auth.dev_sign_in_enabled(), next=request.args.get("next", ""))


@bp.post("/dev-sign-in")
def dev_sign_in():
    if not auth.dev_sign_in_enabled():
        abort(404)
    user_id = int(request.form["user_id"])
    if auth.load_user(user_id) is None:
        abort(400)
    auth.sign_in(user_id)
    nxt = request.form.get("next") or url_for("admin.index")
    return redirect(nxt if nxt.startswith("/") else url_for("admin.index"))


@bp.post("/sign-out")
def sign_out():
    auth.sign_out()
    return redirect(url_for("admin.sign_in_page"))


def _role_permissions(role_code: str) -> "OrderedDict[str, list[dict]]":
    rows = db.fetch_all("""
        SELECT p.area, p.code, p.description
          FROM permissions p
          JOIN roles r ON r.code = :role
         WHERE r.grants_all
            OR EXISTS (SELECT 1 FROM role_permissions rp WHERE rp.role_code = r.code AND rp.permission_code = p.code)
         ORDER BY p.area, p.code
    """, role=role_code)
    grouped: OrderedDict[str, list[dict]] = OrderedDict()
    for row in rows:
        grouped.setdefault(row["area"], []).append(row)
    return grouped


@bp.get("/d/<role_code>")
@auth.login_required
def dashboard(role_code: str):
    user = auth.current_user()
    role = next((r for r in user.roles if r["code"] == role_code), None)
    if role is None:
        abort(403)
    if role_code == "instructor":
        return redirect(url_for("portal.index"))

    perms = {p["code"] for group in _role_permissions(role_code).values() for p in group}
    scope = role["scope_metro_id"]
    panels: dict = {}

    if "class.view" in perms:
        panels["classes"] = db.fetch_all("""
            SELECT s.id, s.starts_at, s.ends_at, s.time_zone, s.status, s.is_published,
                   m.name AS metro_name, si.name AS site_name, cf.name AS course_name,
                   a.sold_seats, a.held_seats, a.seat_limit, a.seats_left, a.waitlist_count,
                   (SELECT i.first_name || ' ' || i.last_name FROM assignments asg
                      JOIN instructors i ON i.id = asg.instructor_id
                     WHERE asg.session_id = s.id AND asg.role = 'lead' AND asg.status = 'assigned') AS lead_name
              FROM sessions s
              JOIN metros m ON m.id = s.metro_id
              JOIN sites si ON si.id = s.site_id
              JOIN course_families cf ON cf.id = s.course_family_id
              JOIN session_availability a ON a.session_id = s.id
             WHERE s.starts_at > now() AND (CAST(:scope AS bigint) IS NULL OR s.metro_id = :scope)
             ORDER BY s.starts_at
             LIMIT 12
        """, scope=scope)

    if "teaching.coverage_view" in perms:
        panels["coverage"] = db.fetch_all("""
            SELECT n.session_id, n.starts_at, n.days_out, n.offer_open,
                   s.time_zone, s.ends_at, si.name AS site_name, cf.name AS course_name, m.name AS metro_name
              FROM sessions_needing_instructor n
              JOIN sessions s ON s.id = n.session_id
              JOIN sites si ON si.id = s.site_id
              JOIN metros m ON m.id = s.metro_id
              JOIN course_families cf ON cf.id = s.course_family_id
             WHERE CAST(:scope AS bigint) IS NULL OR s.metro_id = :scope
             ORDER BY n.starts_at
        """, scope=scope)

    if "waitlist.view" in perms:
        panels["waitlists"] = db.fetch_all("""
            SELECT s.id, s.starts_at, s.time_zone, si.name AS site_name, cf.name AS course_name,
                   a.waitlist_count, s.waitlist_limit, s.location_type
              FROM sessions s
              JOIN sites si ON si.id = s.site_id
              JOIN course_families cf ON cf.id = s.course_family_id
              JOIN session_availability a ON a.session_id = s.id
             WHERE s.starts_at > now() AND a.waitlist_count > 0
               AND (CAST(:scope AS bigint) IS NULL OR s.metro_id = :scope)
             ORDER BY s.starts_at
        """, scope=scope)

    if "system.health_view" in perms:
        panels["health"] = db.fetch_one("""
            SELECT (SELECT count(*) FROM unsynced_items) AS unsynced,
                   (SELECT count(*) FROM integration_issues WHERE resolved_at IS NULL) AS open_issues,
                   (SELECT max(finished_at) FROM integration_runs
                     WHERE kind = 'airtable_sync' AND status IN ('succeeded', 'partial')) AS last_sync_at
        """)

    return render_template("admin/dashboard.html", role=role, permissions=_role_permissions(role_code),
                           perms=perms, panels=panels)
