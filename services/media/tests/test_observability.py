from __future__ import annotations


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
