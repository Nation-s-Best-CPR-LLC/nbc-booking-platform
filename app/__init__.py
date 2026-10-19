"""NBC booking engine: Flask application factory."""

from __future__ import annotations

from flask import Flask, render_template

from . import auth, db, filters
from .config import Config


def create_app(overrides: dict | None = None) -> Flask:
    app = Flask(__name__)
    app.config.from_object(Config)
    if overrides:
        app.config.update(overrides)
    Config.validate(app.config)

    db.init_app(app)
    auth.init_app(app)
    filters.init_app(app)

    # Fixed paths first; the public class finder's /<city>/... routes go last.
    from .blueprints import admin, health, portal, public, webhooks

    app.register_blueprint(health.bp)
    app.register_blueprint(webhooks.bp)
    app.register_blueprint(admin.bp)
    app.register_blueprint(portal.bp)
    app.register_blueprint(public.bp)

    @app.errorhandler(403)
    def forbidden(_e):
        return render_template("errors/error.html", code=403,
                               title="You don't have access to this page",
                               message="Ask an admin to give your account the role this page needs."), 403

    @app.errorhandler(404)
    def not_found(_e):
        return render_template("errors/error.html", code=404, title="Page not found",
                               message="The class may have moved or finished. Start again from the class finder."), 404

    return app
