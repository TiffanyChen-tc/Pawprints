from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = Field(validation_alias="MEDIA_DATABASE_URL")
    jwt_issuer: str = "pawprints-auth"
    jwt_audience: str = "pawprints-api"
    jwt_public_key_path: str
    event_service_url: str = "http://event:8000"
    media_storage_root: str = "/var/lib/pawprints/media"
    media_max_images_per_event: int = 5
    media_max_file_bytes: int = 5_242_880
    media_max_pixels: int = 30_000_000
    media_internal_token: str
    event_internal_token: str

    model_config = SettingsConfigDict(env_prefix="", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
