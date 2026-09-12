from __future__ import annotations

from conftest import create_event


def test_health_readiness_and_metrics_are_safe(client):
    health = client.get("/healthz")
    ready = client.get("/readyz")
    metrics = client.get("/metrics")

    assert health.status_code == 200
    assert health.json() == {"status": "ok"}
    assert "database" not in health.text
    assert "secret" not in health.text
    assert ready.status_code == 200
    assert ready.json() == {"status": "ready"}
    assert metrics.status_code == 200
    assert "pawprints_http_requests_total" in metrics.text


def test_generated_request_id_is_reused_for_downstream_invalidation(client, monkeypatch, token_a, category_a):
    import app.events

    propagated_request_ids = []
    monkeypatch.setattr(
        app.events,
        "invalidate_user_analytics",
        lambda user_id, request_id, settings: propagated_request_ids.append(request_id),
    )

    response = create_event(client, token_a, category_a["id"])

    assert response.status_code == 201
    assert response.headers["X-Request-Id"]
    assert propagated_request_ids == [response.headers["X-Request-Id"]]
