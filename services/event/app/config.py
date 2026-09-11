from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = Field(validation_alias="EVENT_DATABASE_URL")
    jwt_issuer: str = "pawprints-auth"
    jwt_audience: str = "pawprints-api"
    jwt_public_key_path: str
    event_internal_token: str
    media_internal_token: str
    analytics_internal_token: str
    media_service_url: str = "http://media:8000"
    analytics_service_url: str = "http://analytics:8000"

    model_config = SettingsConfigDict(env_prefix="", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
