from __future__ import annotations

from datetime import datetime, timedelta, timezone
import hashlib
import secrets
from uuid import UUID

import jwt
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.serialization import load_pem_private_key

from app.config import Settings


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def hash_refresh_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def new_refresh_token() -> str:
    return secrets.token_urlsafe(48)


def create_access_token(user_id: UUID, settings: Settings) -> str:
    now = utc_now()
    private_key = open(settings.jwt_private_key_path, encoding="utf-8").read()
    payload = {
        "sub": str(user_id),
        "iss": settings.jwt_issuer,
        "aud": settings.jwt_audience,
        "iat": now,
        "exp": now + timedelta(minutes=settings.access_token_ttl_minutes),
    }
    return jwt.encode(payload, private_key, algorithm="RS256")


def public_key_from_private_key(settings: Settings) -> str:
    private_key = load_pem_private_key(open(settings.jwt_private_key_path, "rb").read(), password=None)
    return private_key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode("ascii")
