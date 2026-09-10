from __future__ import annotations

from conftest import bearer, create_event, patch_event


def test_user_b_cannot_create_event_with_user_a_category(client, token_b, category_a):
    response = create_event(client, token_b, category_a["id"])

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "resource_not_found"


def test_user_b_cannot_patch_own_event_to_user_a_category(client, token_b, event_b, category_a):
    response = patch_event(client, token_b, event_b["id"], '"1"', {"category_id": category_a["id"]})

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "resource_not_found"


def test_user_b_cannot_read_update_or_delete_user_a_event(client, token_b, event_a):
    read = client.get(f"/api/v1/events/{event_a['id']}", headers=bearer(token_b))
    update = patch_event(client, token_b, event_a["id"], '"1"', {"title": "Nope"})
    delete = client.delete(f"/api/v1/events/{event_a['id']}", headers={**bearer(token_b), "If-Match": '"1"'})

    assert read.status_code == 404
    assert update.status_code == 404
    assert delete.status_code == 404
    assert read.json()["error"]["code"] == "resource_not_found"
    assert update.json()["error"]["code"] == "resource_not_found"
    assert delete.json()["error"]["code"] == "resource_not_found"


def test_invalid_bearer_token_is_rejected(client):
    response = client.get("/api/v1/categories", headers={"Authorization": "Bearer not-a-jwt"})

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "not_authenticated"
