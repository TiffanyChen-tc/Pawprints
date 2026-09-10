from __future__ import annotations

from conftest import create_event, patch_event


def test_create_get_patch_and_delete_event_with_etags(client, token_a, category_a):
    created = create_event(client, token_a, category_a["id"], latitude=25.05, longitude=121.53)

    assert created.status_code == 201
    assert created.headers["ETag"] == '"1"'
    body = created.json()
    assert body["version"] == 1
    assert body["occurred_at"] == "2026-09-09T00:00:00Z"
    assert body["local_date"] == "2026-09-09"

    fetched = client.get(f"/api/v1/events/{body['id']}", headers={"Authorization": f"Bearer {token_a}"})
    assert fetched.status_code == 200
    assert fetched.headers["ETag"] == '"1"'

    patched = patch_event(
        client,
        token_a,
        body["id"],
        '"1"',
        {"title": "Evening run", "local_datetime": "2026-09-09T18:00:00"},
    )
    assert patched.status_code == 200
    assert patched.headers["ETag"] == '"2"'
    assert patched.json()["occurred_at"] == "2026-09-09T10:00:00Z"

    deleted = client.delete(f"/api/v1/events/{body['id']}", headers={"Authorization": f"Bearer {token_a}", "If-Match": '"2"'})
    assert deleted.status_code == 204


def test_event_rejects_invalid_timezone(client, token_a, category_a):
    response = create_event(client, token_a, category_a["id"], timezone="Not/AZone")

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_failed"


def test_mood_and_location_validation(client, token_a, category_a):
    bad_mood = create_event(client, token_a, category_a["id"], mood="sparkly")
    one_coordinate = create_event(client, token_a, category_a["id"], latitude=12.0)
    bad_latitude = create_event(client, token_a, category_a["id"], latitude=91, longitude=0)
    bad_longitude = create_event(client, token_a, category_a["id"], latitude=0, longitude=181)
    location_only = create_event(client, token_a, category_a["id"], location_name="Park", latitude=None, longitude=None)

    assert bad_mood.status_code == 422
    assert one_coordinate.status_code == 422
    assert bad_latitude.status_code == 422
    assert bad_longitude.status_code == 422
    assert location_only.status_code == 201


def test_patch_recomputes_time_fields(client, token_a, event_a):
    response = patch_event(
        client,
        token_a,
        event_a["id"],
        '"1"',
        {"local_datetime": "2026-09-10T00:30:00", "timezone": "Asia/Taipei"},
    )

    assert response.status_code == 200
    assert response.json()["occurred_at"] == "2026-09-09T16:30:00Z"
    assert response.json()["local_date"] == "2026-09-10"


def test_patch_timezone_only_preserves_original_local_wall_time(client, token_a, category_a):
    created = create_event(
        client,
        token_a,
        category_a["id"],
        local_datetime="2026-09-09T08:00:00",
        timezone="America/New_York",
    ).json()

    response = patch_event(client, token_a, created["id"], '"1"', {"timezone": "UTC"})

    assert response.status_code == 200
    assert response.json()["occurred_at"] == "2026-09-09T08:00:00Z"
    assert response.json()["local_date"] == "2026-09-09"
