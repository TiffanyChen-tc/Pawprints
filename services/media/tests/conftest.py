from __future__ import annotations

from collections.abc import Iterator
from datetime import datetime, timedelta, timezone
import importlib
from io import BytesIO
import os
from pathlib import Path
from typing import TYPE_CHECKING
from uuid import UUID, uuid4
import warnings

import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from PIL import Image
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

if TYPE_CHECKING:
    from fastapi.testclient import TestClient


USER_A = UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa")
USER_B = UUID("bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb")
EVENT_A = UUID("aaaaaaaa-1111-4111-8111-aaaaaaaaaaaa")
EVENT_B = UUID("bbbbbbbb-2222-4222-8222-bbbbbbbbbbbb")


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
    key_path = Path(f"services/media/tests/.tmp-jwt-public-{uuid4()}.pem")
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


@pytest.fixture()
def media_database_url() -> str:
    return os.environ.get(
        "MEDIA_DATABASE_URL",
        "postgresql+psycopg://pawprints_media_rw:test_media@127.0.0.1:55432/pawprints_test",
    )


@pytest.fixture()
def media_db_session(media_database_url: str) -> Iterator[Session]:
    engine = create_engine(media_database_url)
    with engine.begin() as connection:
        tables_exist = connection.execute(text("SELECT to_regclass('media.event_media') IS NOT NULL")).scalar_one()
        if tables_exist:
            connection.execute(text("TRUNCATE media.event_media RESTART IDENTITY CASCADE"))
    factory = sessionmaker(bind=engine)
    with factory() as session:
        yield session
    engine.dispose()


@pytest.fixture()
def storage_root(tmp_path: Path) -> Path:
    return tmp_path / "media"


@pytest.fixture()
def client(
    monkeypatch: pytest.MonkeyPatch,
    jwt_key_pair: tuple[str, str],
    media_database_url: str,
    media_db_session: Session,
    storage_root: Path,
) -> Iterator[TestClient]:
    _, public_key_path = jwt_key_pair
    monkeypatch.setenv("MEDIA_DATABASE_URL", media_database_url)
    monkeypatch.setenv("JWT_PUBLIC_KEY_PATH", public_key_path)
    monkeypatch.setenv("JWT_ISSUER", "pawprints-auth")
    monkeypatch.setenv("JWT_AUDIENCE", "pawprints-api")
    monkeypatch.setenv("EVENT_SERVICE_URL", "http://event.local")
    monkeypatch.setenv("MEDIA_STORAGE_ROOT", str(storage_root))
    monkeypatch.setenv("MEDIA_MAX_IMAGES_PER_EVENT", "5")
    monkeypatch.setenv("MEDIA_MAX_FILE_BYTES", "5242880")
    monkeypatch.setenv("MEDIA_MAX_PIXELS", "30000000")
    monkeypatch.setenv("MEDIA_INTERNAL_TOKEN", "media-secret")
    monkeypatch.setenv("EVENT_INTERNAL_TOKEN", "event-secret")

    import app.config
    import app.db
    import app.event_client
    import app.main
    from starlette.exceptions import StarletteDeprecationWarning

    with warnings.catch_warnings():
        warnings.simplefilter("ignore", StarletteDeprecationWarning)
        from fastapi.testclient import TestClient

    def fake_verify(event_id: UUID, authorization: str, request_id: str = "") -> bool:
        if not authorization.startswith("Bearer "):
            return False
        claims = jwt.decode(authorization.removeprefix("Bearer "), options={"verify_signature": False})
        return (event_id == EVENT_A and claims.get("sub") == str(USER_A)) or (
            event_id == EVENT_B and claims.get("sub") == str(USER_B)
        )

    app.config.get_settings.cache_clear()
    importlib.reload(app.db)
    importlib.reload(app.event_client)
    import app.routes

    importlib.reload(app.routes)
    monkeypatch.setattr(app.event_client.EventClient, "verify_ownership", lambda self, event_id, authorization, request_id="": fake_verify(event_id, authorization, request_id))
    monkeypatch.setattr(app.routes.EventClient, "verify_ownership", lambda self, event_id, authorization, request_id="": fake_verify(event_id, authorization, request_id))
    importlib.reload(app.main)

    with TestClient(app.main.app) as test_client:
        yield test_client


def image_bytes(fmt: str = "PNG", size: tuple[int, int] = (12, 12)) -> bytes:
    image = Image.new("RGB", size, color=(120, 40, 80))
    output = BytesIO()
    image.save(output, format=fmt)
    return output.getvalue()


def upload_images(client: TestClient, token: str, event_id: UUID, images: list[bytes]):
    files = [("files", (f"image-{index}.png", data, "image/png")) for index, data in enumerate(images)]
    return client.post(f"/api/v1/media/events/{event_id}", headers=bearer(token), files=files)
