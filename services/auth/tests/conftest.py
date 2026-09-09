from __future__ import annotations

from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
import importlib
from pathlib import Path
from typing import TYPE_CHECKING
from uuid import uuid4
import warnings

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

if TYPE_CHECKING:
    from fastapi.testclient import TestClient


@pytest.fixture()
def private_key_path() -> Iterator[str]:
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    path = Path(f"services/auth/tests/.tmp-jwt-private-{uuid4()}.pem")
    path.write_text(
        private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        ).decode("ascii"),
        encoding="ascii",
    )
    try:
        yield str(path)
    finally:
        path.unlink(missing_ok=True)


@pytest.fixture()
def auth_database_url() -> str:
    return "postgresql+psycopg://pawprints_auth_rw:test_auth@127.0.0.1:55432/pawprints_test"


@pytest.fixture()
def auth_db_session(auth_database_url: str) -> Iterator[Session]:
    engine = create_engine(auth_database_url)
    with engine.begin() as connection:
        tables_exist = connection.execute(
            text("SELECT to_regclass('auth.refresh_tokens') IS NOT NULL AND to_regclass('auth.users') IS NOT NULL")
        ).scalar_one()
        if tables_exist:
            connection.execute(text("TRUNCATE auth.refresh_tokens, auth.users RESTART IDENTITY CASCADE"))
    session_factory = sessionmaker(bind=engine)
    with session_factory() as session:
        yield session
    engine.dispose()


@pytest.fixture()
def client(monkeypatch: pytest.MonkeyPatch, private_key_path: str, auth_database_url: str, auth_db_session: Session) -> Iterator[TestClient]:
    monkeypatch.setenv("AUTH_DATABASE_URL", auth_database_url)
    monkeypatch.setenv("JWT_PRIVATE_KEY_PATH", private_key_path)
    monkeypatch.setenv("JWT_ISSUER", "pawprints-auth")
    monkeypatch.setenv("JWT_AUDIENCE", "pawprints-api")
    monkeypatch.setenv("ACCESS_TOKEN_TTL_MINUTES", "15")
    monkeypatch.setenv("REFRESH_SESSION_TTL_DAYS", "7")
    monkeypatch.setenv("COOKIE_SECURE", "false")
    monkeypatch.setenv("COOKIE_SAMESITE", "strict")
    monkeypatch.setenv("COOKIE_DOMAIN", "")
    monkeypatch.setenv("AUTH_ALLOWED_ORIGINS", "http://localhost:8080,http://localhost:5173")

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


def register_user(client: TestClient, email: str = "user@example.com", password: str = "correct horse battery"):
    return client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": password, "display_name": "User"},
    )


def login_user(client: TestClient, email: str = "user@example.com", password: str = "correct horse battery"):
    return client.post("/api/v1/auth/login", json={"email": email, "password": password})


def set_refresh_expired(auth_db_session: Session, token_hash: str) -> None:
    auth_db_session.execute(
        text("UPDATE auth.refresh_tokens SET expires_at = :expires_at WHERE token_hash = :token_hash"),
        {"expires_at": datetime.now(timezone.utc) - timedelta(seconds=1), "token_hash": token_hash},
    )
    auth_db_session.commit()


def run_two_refresh_requests(client: TestClient, cookies) -> list[int]:
    def refresh_once() -> int:
        response = client.post(
            "/api/v1/auth/refresh",
            headers={"Origin": "http://localhost:8080"},
            cookies=cookies,
        )
        return response.status_code

    with ThreadPoolExecutor(max_workers=2) as executor:
        return list(executor.map(lambda _: refresh_once(), range(2)))
