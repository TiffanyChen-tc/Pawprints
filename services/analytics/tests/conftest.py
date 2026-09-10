from __future__ import annotations

from collections.abc import Iterator
from datetime import date, datetime, timedelta, timezone
import importlib
import os
from pathlib import Path
from uuid import UUID, uuid4
import warnings

import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from redis import Redis
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine


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
    key_path = Path(f"/tmp/pawprints-analytics-{uuid4()}.pem")
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
    return make_token(jwt_key_pair[0], USER_A)


@pytest.fixture()
def token_b(jwt_key_pair: tuple[str, str]) -> str:
    return make_token(jwt_key_pair[0], USER_B)


def bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(scope="session")
def event_engine() -> Iterator[Engine]:
    url = os.environ.get(
        "EVENT_DATABASE_URL",
        "postgresql+psycopg://pawprints_event_rw:test_event@127.0.0.1:55432/pawprints_test",
    )
    engine = create_engine(url)
    yield engine
    engine.dispose()


@pytest.fixture(scope="session")
def analytics_database_url() -> str:
    return os.environ.get(
        "ANALYTICS_DATABASE_URL",
        "postgresql+psycopg://pawprints_analytics_ro:test_analytics@127.0.0.1:55432/pawprints_test",
    )


@pytest.fixture(scope="session")
def redis_url() -> str:
    return os.environ.get("REDIS_URL", "redis://127.0.0.1:56379/0")


@pytest.fixture()
def redis_client(redis_url: str) -> Iterator[Redis]:
    client = Redis.from_url(redis_url, decode_responses=True)
    client.flushdb()
    yield client
    client.flushdb()
    client.close()


@pytest.fixture(autouse=True)
def clean_events(event_engine: Engine) -> Iterator[None]:
    with event_engine.begin() as connection:
        connection.execute(text("TRUNCATE events.events, events.categories CASCADE"))
    yield


def insert_fact(
    event_engine: Engine,
    *,
    user_id: UUID,
    category_id: UUID,
    category_name: str,
    local_date: date,
    occurred_at: datetime | None = None,
) -> UUID:
    event_id = uuid4()
    with event_engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO events.categories "
                "(id, user_id, name, normalized_name, version, created_at, updated_at) "
                "VALUES (:id, :user_id, :name, :normalized_name, 1, now(), now()) "
                "ON CONFLICT (id) DO NOTHING"
            ),
            {
                "id": category_id,
                "user_id": user_id,
                "name": category_name,
                "normalized_name": category_name.casefold(),
            },
        )
        connection.execute(
            text(
                "INSERT INTO events.events "
                "(id, user_id, category_id, title, occurred_at, timezone, local_date, version, created_at, updated_at) "
                "VALUES (:id, :user_id, :category_id, :title, :occurred_at, 'UTC', :local_date, 1, now(), now())"
            ),
            {
                "id": event_id,
                "user_id": user_id,
                "category_id": category_id,
                "title": f"Fact {event_id}",
                "occurred_at": occurred_at or datetime.combine(local_date, datetime.min.time(), timezone.utc),
                "local_date": local_date,
            },
        )
    return event_id


@pytest.fixture()
def client(
    monkeypatch: pytest.MonkeyPatch,
    jwt_key_pair: tuple[str, str],
    analytics_database_url: str,
    redis_url: str,
    redis_client: Redis,
):
    monkeypatch.setenv("ANALYTICS_DATABASE_URL", analytics_database_url)
    monkeypatch.setenv("REDIS_URL", redis_url)
    monkeypatch.setenv("ANALYTICS_CACHE_TTL_SECONDS", "600")
    monkeypatch.setenv("JWT_PUBLIC_KEY_PATH", jwt_key_pair[1])
    monkeypatch.setenv("JWT_ISSUER", "pawprints-auth")
    monkeypatch.setenv("JWT_AUDIENCE", "pawprints-api")
    monkeypatch.setenv("EVENT_INTERNAL_TOKEN", "event-secret")

    import app.cache
    import app.config
    import app.db
    import app.internal
    import app.main
    import app.routes

    app.config.get_settings.cache_clear()
    importlib.reload(app.db)
    importlib.reload(app.cache)
    importlib.reload(app.routes)
    importlib.reload(app.internal)
    importlib.reload(app.main)

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        from fastapi.testclient import TestClient

        with TestClient(app.main.app) as test_client:
            yield test_client
    app.db.engine.dispose()
