from __future__ import annotations

from collections.abc import Iterator
from datetime import datetime, timedelta, timezone
import importlib
import os
from pathlib import Path
from typing import TYPE_CHECKING
from uuid import UUID, uuid4
import warnings

import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

if TYPE_CHECKING:
    from fastapi.testclient import TestClient


PASSWORD = "correct horse battery"
USER_A = UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa")
USER_B = UUID("bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb")


@pytest.fixture(scope="session")
def jwt_key_pair() -> Iterator[tuple[str, str]]:
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode("ascii")
    public_pem = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode("ascii")
    key_path = Path(f"services/event/tests/.tmp-jwt-public-{uuid4()}.pem")
    key_path.write_text(public_pem, encoding="ascii")
    try:
        yield private_pem, str(key_path)
    finally:
        key_path.unlink(missing_ok=True)


def make_token(private_pem: str, user_id: UUID) -> str:
    now = datetime.now(timezone.utc)
    return jwt.encode(
        {
            "sub": str(user_id),
            "iss": "pawprints-auth",
            "aud": "pawprints-api",
            "iat": now,
            "exp": now + timedelta(minutes=15),
        },
        private_pem,
        algorithm="RS256",
    )


@pytest.fixture()
def token_a(jwt_key_pair: tuple[str, str]) -> str:
    private_pem, _ = jwt_key_pair
    return make_token(private_pem, USER_A)


@pytest.fixture()
def token_b(jwt_key_pair: tuple[str, str]) -> str:
    private_pem, _ = jwt_key_pair
    return make_token(private_pem, USER_B)


def bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture()
def event_database_url() -> str:
    return os.environ.get(
        "EVENT_DATABASE_URL",
        "postgresql+psycopg://pawprints_event_rw:test_event@127.0.0.1:55432/pawprints_test",
    )


@pytest.fixture()
def event_db_session(event_database_url: str) -> Iterator[Session]:
    engine = create_engine(event_database_url)
    with engine.begin() as connection:
        tables_exist = connection.execute(
            text("SELECT to_regclass('events.events') IS NOT NULL AND to_regclass('events.categories') IS NOT NULL")
        ).scalar_one()
        if tables_exist:
            connection.execute(text("TRUNCATE events.events, events.categories RESTART IDENTITY CASCADE"))
    session_factory = sessionmaker(bind=engine)
    with session_factory() as session:
        yield session
    engine.dispose()


@pytest.fixture()
def client(monkeypatch: pytest.MonkeyPatch, jwt_key_pair: tuple[str, str], event_database_url: str, event_db_session: Session) -> Iterator[TestClient]:
    _, public_key_path = jwt_key_pair
    monkeypatch.setenv("EVENT_DATABASE_URL", event_database_url)
    monkeypatch.setenv("JWT_PUBLIC_KEY_PATH", public_key_path)
    monkeypatch.setenv("JWT_ISSUER", "pawprints-auth")
    monkeypatch.setenv("JWT_AUDIENCE", "pawprints-api")
    monkeypatch.setenv("MEDIA_INTERNAL_TOKEN", "media-secret")
    monkeypatch.setenv("EVENT_INTERNAL_TOKEN", "event-secret")
    monkeypatch.setenv("ANALYTICS_INTERNAL_TOKEN", "analytics-secret")
    monkeypatch.setenv("ANALYTICS_SERVICE_URL", "http://analytics.local")

    import app.config
    import app.db
    import app.main
    from starlette.exceptions import StarletteDeprecationWarning

    with warnings.catch_warnings():
        warnings.simplefilter("ignore", StarletteDeprecationWarning)
        from fastapi.testclient import TestClient

    app.config.get_settings.cache_clear()
    importlib.reload(app.db)
    importlib.reload(app.main)

    with TestClient(app.main.app) as test_client:
        yield test_client


def create_category(client: TestClient, token: str, name: str = "Running"):
    return client.post("/api/v1/categories", headers=bearer(token), json={"name": name})


def rename_category(client: TestClient, token: str, category_id: str, if_match: str | None, name: str = "Jogging"):
    headers = bearer(token)
    if if_match is not None:
        headers["If-Match"] = if_match
    return client.patch(f"/api/v1/categories/{category_id}", headers=headers, json={"name": name})


def valid_event_body(category_id: str, **overrides):
    body = {
        "title": "Morning run",
        "category_id": category_id,
        "local_datetime": "2026-09-09T08:00:00",
        "timezone": "Asia/Taipei",
        "description": "Easy miles",
        "mood": "good",
        "location_name": "Riverside",
    }
    body.update(overrides)
    return body


def create_event(client: TestClient, token: str, category_id: str, **overrides):
    return client.post("/api/v1/events", headers=bearer(token), json=valid_event_body(category_id, **overrides))


def patch_event(client: TestClient, token: str, event_id: str, if_match: str | None, body: dict):
    headers = bearer(token)
    if if_match is not None:
        headers["If-Match"] = if_match
    return client.patch(f"/api/v1/events/{event_id}", headers=headers, json=body)


@pytest.fixture()
def category_a(client: TestClient, token_a: str):
    return create_category(client, token_a, "Running").json()


@pytest.fixture()
def category_b(client: TestClient, token_b: str):
    return create_category(client, token_b, "Reading").json()


@pytest.fixture()
def event_a(client: TestClient, token_a: str, category_a):
    return create_event(client, token_a, category_a["id"]).json()


@pytest.fixture()
def event_b(client: TestClient, token_b: str, category_b):
    return create_event(client, token_b, category_b["id"]).json()
