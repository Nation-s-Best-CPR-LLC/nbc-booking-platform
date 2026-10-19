"""Settings, read from environment variables (Replit Secrets in staging/production)."""

from __future__ import annotations

import os


class ConfigError(RuntimeError):
    """Raised at start-up when a required setting is missing or unsafe."""


def _bool(name: str, default: bool = False) -> bool:
    return os.environ.get(name, str(default)).strip().lower() in {"1", "true", "yes", "on"}


class Config:
    # local | staging | production. Must match app_settings.environment in the database.
    APP_ENV = os.environ.get("APP_ENV", "local")

    SECRET_KEY = os.environ.get("SECRET_KEY", "")
    DATABASE_URL = os.environ.get("DATABASE_URL", "")

    # Public site address, used in canonical links and structured data.
    PUBLIC_BASE_URL = os.environ.get("PUBLIC_BASE_URL", "http://localhost:5000")

    # Local development only: lets you sign in as a seeded account without
    # Microsoft 365 or an emailed link. Refused outside APP_ENV=local.
    DEV_SIGN_IN = _bool("DEV_SIGN_IN", default=False)

    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"

    # Set by the static preview exporter; adds a banner to every page.
    PREVIEW_MODE = False

    @classmethod
    def validate(cls, cfg: dict) -> None:
        env = cfg["APP_ENV"]
        if env not in {"local", "staging", "production"}:
            raise ConfigError(f"APP_ENV must be local, staging or production, not {env!r}")
        if not cfg.get("DATABASE_URL"):
            raise ConfigError("DATABASE_URL is not set")
        if env != "local":
            if len(cfg.get("SECRET_KEY") or "") < 32:
                raise ConfigError("SECRET_KEY must be set (32+ characters) outside local development")
            if cfg.get("DEV_SIGN_IN"):
                raise ConfigError("DEV_SIGN_IN may only be used with APP_ENV=local")
            cfg["SESSION_COOKIE_SECURE"] = True
        elif not cfg.get("SECRET_KEY"):
            cfg["SECRET_KEY"] = "local-development-only"
