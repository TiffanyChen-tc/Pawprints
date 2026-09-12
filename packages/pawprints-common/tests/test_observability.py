from __future__ import annotations

import json
import logging
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient

from pawprints_common.observability import install_request_context_and_metrics


def _metric_samples(metrics_text: str, metric_name: str):
    from prometheus_client.parser import text_string_to_metric_families

    for family in text_string_to_metric_families(metrics_text):
        if family.name == metric_name:
            return family.samples
    return []


def test_request_log_uses_consistent_request_id_and_excludes_sensitive_values(caplog):
    app = FastAPI()
    install_request_context_and_metrics(app, "unit")

    @app.post("/api/v1/events/{event_id}")
    def create_event(event_id: str, body: dict):
        return {"event_id": event_id, "description": body["description"]}

    caplog.set_level(logging.INFO, logger="pawprints.requests")

    response = TestClient(app).post(
        "/api/v1/events/aaaaaaaa-1111-4111-8111-aaaaaaaaaaaa?token=query-secret",
        headers={
            "X-Request-Id": "edge-request-13",
            "Authorization": "Bearer header-secret",
        },
        json={"description": "private diary words"},
    )

    assert response.status_code == 200
    assert response.headers["X-Request-Id"] == "edge-request-13"
    record = caplog.records[-1]
    payload = json.loads(record.message)
    assert payload["event"] == "http_request"
    assert payload["request_id"] == "edge-request-13"
    assert payload["service"] == "unit"
    assert payload["level"] == "info"
    assert payload["method"] == "POST"
    assert payload["route"] == "/api/v1/events/{event_id}"
    assert payload["status"] == 200
    assert payload["latency_ms"] >= 0
    rendered = record.message
    assert "header-secret" not in rendered
    assert "query-secret" not in rendered
    assert "private diary words" not in rendered
    assert "aaaaaaaa-1111-4111-8111-aaaaaaaaaaaa" not in rendered


def test_request_id_is_generated_when_absent_and_metrics_record_low_cardinality_labels():
    app = FastAPI()
    install_request_context_and_metrics(app, "unit")

    @app.get("/api/v1/media/{media_id}")
    def read_media(media_id: str):
        return {"id": media_id}

    client = TestClient(app)
    before = client.get("/metrics").text

    response = client.get("/api/v1/media/bbbbbbbb-2222-4222-8222-bbbbbbbbbbbb")

    assert response.status_code == 200
    assert response.headers["X-Request-Id"]
    metrics = client.get("/metrics").text
    assert "pawprints_http_request_duration_seconds_bucket" in metrics
    samples = _metric_samples(metrics, "pawprints_http_requests")
    sample = next(
        sample
        for sample in samples
        if sample.labels.get("service") == "unit"
        and sample.labels.get("method") == "GET"
        and sample.labels.get("route") == "/api/v1/media/{media_id}"
        and sample.labels.get("status_code") == "200"
    )
    assert sample.value >= 1
    assert metrics != before
    assert "media_id" not in sample.labels
    assert "user_id" not in sample.labels
    assert "bbbbbbbb-2222-4222-8222-bbbbbbbbbbbb" not in metrics


def test_error_metrics_record_safe_error_code():
    app = FastAPI()
    install_request_context_and_metrics(app, "unit")

    @app.get("/api/v1/fails")
    def fail():
        return JSONResponse(
            {"error": {"code": "validation_failed", "message": "Some fields are invalid."}},
            status_code=422,
        )

    client = TestClient(app)

    response = client.get("/api/v1/fails")

    assert response.status_code == 422
    samples = _metric_samples(client.get("/metrics").text, "pawprints_http_requests")
    assert any(
        sample.labels.get("error_code") == "validation_failed"
        and sample.labels.get("status_code") == "422"
        for sample in samples
    )


def test_prometheus_and_grafana_provisioning_targets_are_declared():
    prometheus_config = Path("infra/prometheus/prometheus.yml").read_text(encoding="utf-8")
    assert "auth:8000" in prometheus_config
    assert "event:8000" in prometheus_config
    assert "media:8000" in prometheus_config
    assert "analytics:8000" in prometheus_config
    assert "/metrics" in prometheus_config

    datasource = Path("infra/grafana/provisioning/datasources/prometheus.yml").read_text(encoding="utf-8")
    dashboard_provider = Path("infra/grafana/provisioning/dashboards/dashboards.yml").read_text(encoding="utf-8")
    dashboard = Path("infra/grafana/dashboards/pawprints-service-overview.json").read_text(encoding="utf-8")
    compose = Path("compose.yaml").read_text(encoding="utf-8")

    assert "http://prometheus:9090" in datasource
    assert "/var/lib/grafana/dashboards" in dashboard_provider
    assert '"title": "Pawprints Service Overview"' in dashboard
    assert "prometheus:" in compose
    assert "grafana:" in compose
