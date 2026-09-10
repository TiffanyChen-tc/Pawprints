from __future__ import annotations

from conftest import patch_event


def test_patch_requires_if_match(client, token_a, event_a):
    response = patch_event(client, token_a, event_a["id"], None, {"title": "Changed"})

    assert response.status_code == 428
    assert response.json()["error"]["code"] == "precondition_required"


def test_delete_requires_if_match(client, token_a, event_a):
    response = client.delete(f"/api/v1/events/{event_a['id']}", headers={"Authorization": f"Bearer {token_a}"})

    assert response.status_code == 428
    assert response.json()["error"]["code"] == "precondition_required"


def test_stale_if_match_returns_412_without_leaking_foreign_versions(client, token_a, token_b, event_a):
    first = patch_event(client, token_a, event_a["id"], '"1"', {"title": "First"})
    stale = patch_event(client, token_a, event_a["id"], '"1"', {"title": "Second"})
    foreign = patch_event(client, token_b, event_a["id"], '"1"', {"title": "Foreign"})

    assert first.status_code == 200
    assert stale.status_code == 412
    assert stale.json()["error"]["code"] == "stale_version"
    assert foreign.status_code == 404
    assert foreign.json()["error"]["code"] == "resource_not_found"


def test_stale_delete_returns_412_for_owner(client, token_a, event_a):
    patch_event(client, token_a, event_a["id"], '"1"', {"title": "First"})

    stale = client.delete(f"/api/v1/events/{event_a['id']}", headers={"Authorization": f"Bearer {token_a}", "If-Match": '"1"'})

    assert stale.status_code == 412
    assert stale.json()["error"]["code"] == "stale_version"
