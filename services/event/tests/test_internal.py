from __future__ import annotations

from conftest import bearer


def internal_headers(token: str, caller: str = "media", internal_token: str = "media-secret") -> dict[str, str]:
    return {
        **bearer(token),
        "X-Pawprints-Internal-Service": caller,
        "X-Pawprints-Internal-Token": internal_token,
        "X-Request-Id": "request-1",
    }


def test_internal_ownership_requires_media_internal_credentials(client, token_a, event_a):
    missing = client.get(f"/internal/events/{event_a['id']}/ownership", headers=bearer(token_a))
    wrong = client.get(f"/internal/events/{event_a['id']}/ownership", headers=internal_headers(token_a, internal_token="wrong"))
    wrong_caller = client.get(f"/internal/events/{event_a['id']}/ownership", headers=internal_headers(token_a, caller="event"))

    assert missing.status_code == 401
    assert wrong.status_code == 401
    assert wrong_caller.status_code == 401


def test_internal_ownership_returns_success_for_owned_event(client, token_a, event_a):
    response = client.get(f"/internal/events/{event_a['id']}/ownership", headers=internal_headers(token_a))

    assert response.status_code == 200
    assert response.json() == {"event_id": event_a["id"], "user_id": "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"}


def test_internal_ownership_uses_safe_404_for_foreign_or_missing(client, token_b, event_a):
    response = client.get(f"/internal/events/{event_a['id']}/ownership", headers=internal_headers(token_b))

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "resource_not_found"
