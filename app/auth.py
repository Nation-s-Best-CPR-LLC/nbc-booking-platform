"""Who is signed in, and what they may do.

Accounts, roles and permissions live in the database (user_accounts,
user_roles, role_permissions). Every check goes through the database's own
user_has_permission() so the app and the schema can never disagree.

Sign-in methods (to be built):
  * Staff: Microsoft 365 (Entra ID), phase 4b.
  * Instructors: one-time emailed link, phase 4c.
Until then, local development can use DEV_SIGN_IN (refused outside local).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from functools import wraps
from typing import Callable

from flask import Flask, abort, current_app, g, redirect, request, session, url_for

from . import db


@dataclass
class CurrentUser:
    id: int
    email: str
    display_name: str
    roles: list[dict] = field(default_factory=list)          # [{code, name, dashboard_key, scope_metro_id}]
    permissions: set[str] = field(default_factory=set)        # permission codes held anywhere

    @property
    def role_codes(self) -> list[str]:
        return [r["code"] for r in self.roles]

    def can(self, permission: str, metro_id: int | None = None) -> bool:
        """Exact check in the database (honours city-area limits)."""
        return bool(db.fetch_value(
            "SELECT user_has_permission(:uid, :perm, :metro)",
            uid=self.id, perm=permission, metro=metro_id,
        ))

    def has_any(self, permission: str) -> bool:
        """Cheap check for menus: does any role grant this permission at all?"""
        return permission in self.permissions


def load_user(user_id: int) -> CurrentUser | None:
    account = db.fetch_one(
        "SELECT id, email, display_name FROM user_accounts WHERE id = :id AND status = 'active'",
        id=user_id,
    )
    if not account:
        return None
    roles = db.fetch_all(
        """
        SELECT r.code, r.name, r.dashboard_key, r.description, ur.scope_metro_id, m.name AS scope_metro_name
          FROM user_roles ur
          JOIN roles r ON r.code = ur.role_code
          LEFT JOIN metros m ON m.id = ur.scope_metro_id
         WHERE ur.user_account_id = :id AND ur.revoked_at IS NULL
         ORDER BY r.sort_order
        """,
        id=user_id,
    )
    perms = {r["permission_code"] for r in db.fetch_all(
        "SELECT DISTINCT permission_code FROM user_effective_permissions WHERE user_account_id = :id",
        id=user_id,
    )}
    return CurrentUser(id=account["id"], email=account["email"], display_name=account["display_name"],
                       roles=roles, permissions=perms)


def current_user() -> CurrentUser | None:
    if "current_user" not in g:
        uid = session.get("user_id")
        g.current_user = load_user(uid) if uid else None
    return g.current_user


def sign_in(user_id: int) -> None:
    session.clear()
    session["user_id"] = user_id


def sign_out() -> None:
    session.clear()
    g.pop("current_user", None)


def login_required(view: Callable) -> Callable:
    @wraps(view)
    def wrapped(*args, **kwargs):
        if current_user() is None:
            return redirect(url_for("admin.sign_in_page", next=request.path))
        return view(*args, **kwargs)
    return wrapped


def permission_required(permission: str) -> Callable:
    """Require a permission (in any city area; check the exact area inside the view)."""
    def decorator(view: Callable) -> Callable:
        @wraps(view)
        @login_required
        def wrapped(*args, **kwargs):
            if not current_user().has_any(permission):
                abort(403)
            return view(*args, **kwargs)
        return wrapped
    return decorator


def dev_sign_in_enabled() -> bool:
    return bool(current_app.config.get("DEV_SIGN_IN")) and current_app.config["APP_ENV"] == "local"


def init_app(app: Flask) -> None:
    @app.context_processor
    def inject_user():
        return {"current_user": current_user()}
