from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = Field(validation_alias="ANALYTICS_DATABASE_URL")
    redis_url: str = Field(validation_alias="REDIS_URL")
    analytics_cache_ttl_seconds: int = 600
    jwt_issuer: str = "pawprints-auth"
    jwt_audience: str = "pawprints-api"
    jwt_public_key_path: str
    event_internal_token: str

    model_config = SettingsConfigDict(env_prefix="", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
