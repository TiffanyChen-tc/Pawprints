from __future__ import annotations


class _ReadinessConnection:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def execute(self, statement):
        if "events.analytics_event_facts" not in str(statement):
            raise RuntimeError("read view was not checked")


class _ReadinessEngine:
    def connect(self):
        return _ReadinessConnection()


def test_health_readiness_and_metrics_are_safe_when_redis_is_available(client):
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


def test_readiness_checks_analytics_event_facts_view(client, monkeypatch):
    import app.main

    monkeypatch.setattr(app.main, "engine", _ReadinessEngine())

    response = client.get("/readyz")

    assert response.status_code == 200
    assert response.json() == {"status": "ready"}
