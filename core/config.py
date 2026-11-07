from __future__ import annotations

import os
from dataclasses import dataclass


def _as_bool(value: str | None, *, default: bool = False) -> bool:
    if value is None:
        return default
    return value.lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    app_name: str
    secret_key: str
    database_url: str
    session_https_only: bool
    github_client_id: str | None
    github_client_secret: str | None


def get_settings() -> Settings:
    return Settings(
        app_name="FlowTask",
        secret_key=os.getenv("APP_SECRET_KEY", "dev-only-change-me-before-deploy"),
        database_url=os.getenv("DATABASE_URL", "sqlite:///./database.db"),
        session_https_only=_as_bool(os.getenv("SESSION_HTTPS_ONLY")),
        github_client_id=os.getenv("GITHUB_CLIENT_ID"),
        github_client_secret=os.getenv("GITHUB_CLIENT_SECRET"),
    )


settings = get_settings()

