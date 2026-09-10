from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

import pytest
from sqlalchemy.exc import IntegrityError

from app.models import EventMedia
from app.storage import LocalFileStorage
from conftest import EVENT_A, bearer, image_bytes, upload_images


def test_upload_appends_display_order_and_preserves_batch_order(client, token_a):
    first = upload_images(client, token_a, EVENT_A, [image_bytes(), image_bytes()])
    second = upload_images(client, token_a, EVENT_A, [image_bytes("JPEG"), image_bytes("WEBP")])

    assert first.status_code == 201
    assert second.status_code == 201
    assert [m["display_order"] for m in first.json()] == [1, 2]
    assert [m["display_order"] for m in second.json()] == [3, 4]


def test_max_five_enforced(client, token_a):
    assert upload_images(client, token_a, EVENT_A, [image_bytes()] * 5).status_code == 201
    rejected = upload_images(client, token_a, EVENT_A, [image_bytes()])

    assert rejected.status_code == 409
    assert rejected.json()["error"]["code"] == "media_limit_exceeded"


def test_delete_does_not_renumber_remaining_images(client, token_a):
    created = upload_images(client, token_a, EVENT_A, [image_bytes()] * 3).json()
    response = client.delete(f"/api/v1/media/{created[1]['id']}", headers=bearer(token_a))

    assert response.status_code == 204
    listed = client.get(f"/api/v1/media/events/{EVENT_A}", headers=bearer(token_a)).json()
    assert [item["display_order"] for item in listed] == [1, 3]


def test_internal_cleanup_is_authenticated_and_idempotent(client, token_a):
    upload_images(client, token_a, EVENT_A, [image_bytes()] * 2)
    unauthenticated = client.post(f"/internal/media/events/{EVENT_A}/cleanup")
    first = client.post(
        f"/internal/media/events/{EVENT_A}/cleanup",
        headers={"X-Pawprints-Internal-Service": "event", "X-Pawprints-Internal-Token": "event-secret"},
    )
    second = client.post(
        f"/internal/media/events/{EVENT_A}/cleanup",
        headers={"X-Pawprints-Internal-Service": "event", "X-Pawprints-Internal-Token": "event-secret"},
    )

    assert unauthenticated.status_code == 401
    assert first.status_code == 200
    assert second.status_code == 200
    assert client.get(f"/api/v1/media/events/{EVENT_A}", headers=bearer(token_a)).json() == []


def test_retrieval_streams_private_bytes(client, token_a):
    created = upload_images(client, token_a, EVENT_A, [image_bytes()]).json()[0]
    response = client.get(f"/api/v1/media/{created['id']}", headers=bearer(token_a))

    assert response.status_code == 200
    assert response.headers["content-type"] == "image/png"
    assert response.content.startswith(b"\x89PNG")


def test_local_file_storage_read_streams_chunks(storage_root):
    file_storage = LocalFileStorage(storage_root)
    key = file_storage.generate_key()
    file_storage.write(key, b"abc")

    stream = file_storage.read(key)

    assert iter(stream) is stream
    assert b"".join(stream) == b"abc"


def test_delete_storage_failure_preserves_metadata_for_retry(client, token_a, monkeypatch, media_db_session):
    import app.routes

    created = upload_images(client, token_a, EVENT_A, [image_bytes()]).json()[0]

    def fail_delete(self, key):
        raise OSError("disk unavailable")

    monkeypatch.setattr(app.routes.LocalFileStorage, "delete", fail_delete)
    response = client.delete(f"/api/v1/media/{created['id']}", headers=bearer(token_a))

    assert response.status_code == 500
    assert media_db_session.get(EventMedia, UUID(created["id"])) is not None


def test_unique_event_display_order_constraint_rejects_duplicates(media_db_session):
    first = EventMedia(
        event_id=EVENT_A,
        storage_key="first-key",
        mime_type="image/png",
        file_size=1,
        display_order=1,
        created_at=datetime.now(timezone.utc),
    )
    duplicate = EventMedia(
        event_id=EVENT_A,
        storage_key="second-key",
        mime_type="image/png",
        file_size=1,
        display_order=1,
        created_at=datetime.now(timezone.utc),
    )

    media_db_session.add(first)
    media_db_session.flush()
    media_db_session.add(duplicate)
    with pytest.raises(IntegrityError):
        media_db_session.flush()
