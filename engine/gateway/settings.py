"""Process settings loaded from DDE_* environment variables."""

from __future__ import annotations

import os
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime settings for DDE Core."""

    model_config = SettingsConfigDict(env_prefix="DDE_", extra="forbid")

    database_url: str
    redis_url: str


def settings_from_env() -> Settings:
    """Construct settings from DDE_* environment variables."""
    return Settings.model_validate(
        {
            "database_url": os.environ.get("DDE_DATABASE_URL"),
            "redis_url": os.environ.get("DDE_REDIS_URL"),
        }
    )


@lru_cache
def get_settings() -> Settings:
    """Load settings once per process."""
    return settings_from_env()
