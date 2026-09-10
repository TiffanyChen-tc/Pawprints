from __future__ import annotations

from conftest import EVENT_A, EVENT_B, bearer, image_bytes, upload_images


def test_user_b_cannot_upload_media_to_user_a_event(client, token_b):
    response = upload_images(client, token_b, EVENT_A, [image_bytes()])

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "resource_not_found"


def test_user_b_cannot_list_retrieve_or_delete_user_a_media(client, token_a, token_b):
    media = upload_images(client, token_a, EVENT_A, [image_bytes()]).json()[0]

    listing = client.get(f"/api/v1/media/events/{EVENT_A}", headers=bearer(token_b))
    retrieve = client.get(f"/api/v1/media/{media['id']}", headers=bearer(token_b))
    delete = client.delete(f"/api/v1/media/{media['id']}", headers=bearer(token_b))

    assert listing.status_code == 404
    assert retrieve.status_code == 404
    assert delete.status_code == 404
    assert listing.json()["error"]["code"] == "resource_not_found"


def test_public_media_json_does_not_expose_storage_key_or_path(client, token_a):
    response = upload_images(client, token_a, EVENT_A, [image_bytes()])
    body = response.json()[0]

    assert "storage_key" not in body
    assert "path" not in body
    assert set(body) == {"id", "event_id", "mime_type", "file_size", "display_order", "created_at"}


def test_user_a_cannot_access_media_by_guessing_other_event_id(client, token_a, token_b):
    upload_images(client, token_b, EVENT_B, [image_bytes()])

    response = client.get(f"/api/v1/media/events/{EVENT_B}", headers=bearer(token_a))

    assert response.status_code == 404
