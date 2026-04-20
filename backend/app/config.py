"""App configuration, loaded from environment (.env in dev)."""

from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    supabase_url: str = Field(...)
    supabase_anon_key: str = Field(...)
    supabase_service_key: str = Field(...)
    supabase_jwt_secret: str = Field(...)

    frontend_origins: str = "http://localhost:3007"
    app_env: str = "development"

    @property
    def cors_origins(self) -> list[str]:
        return [o.strip() for o in self.frontend_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]  # values come from env
