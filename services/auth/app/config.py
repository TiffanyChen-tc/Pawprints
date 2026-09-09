from __future__ import annotations

from functools import lru_cache

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = Field(validation_alias="AUTH_DATABASE_URL")
    environment: str = "local"
    jwt_issuer: str = "pawprints-auth"
    jwt_audience: str = "pawprints-api"
    jwt_private_key_path: str
    access_token_ttl_minutes: int = 15
    refresh_session_ttl_days: int = 7
    cookie_secure: bool = False
    cookie_samesite: str = "strict"
    cookie_domain: str = ""
    auth_allowed_origins: str = "http://localhost:8080,http://localhost:5173"

    model_config = SettingsConfigDict(env_prefix="", extra="ignore")

    @property
    def allowed_origins(self) -> set[str]:
        return {origin.strip() for origin in self.auth_allowed_origins.split(",") if origin.strip()}

    @model_validator(mode="after")
    def require_secure_cookies_in_production(self) -> Settings:
        if self.environment.lower() == "production" and not self.cookie_secure:
            raise ValueError("COOKIE_SECURE must be true in production")
        return self

@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
