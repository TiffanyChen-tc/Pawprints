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


def test_grafana_service_overview_dashboard_covers_red_status_and_route_panels():
    dashboard_path = Path("infra/grafana/dashboards/pawprints-service-overview.json")
    dashboard = json.loads(dashboard_path.read_text(encoding="utf-8"))
    application_route_filter = 'route!~"^/(healthz|readyz|metrics)$"'

    panels = {panel["title"]: panel for panel in dashboard["panels"]}
    assert set(panels) == {
        "Request Rate",
        "5xx Ratio",
        "P95 Latency",
        "Service Status",
        "4xx Ratio",
        "Latency Percentiles",
        "Requests by Route",
    }

    assert panels["Request Rate"]["gridPos"] == {"h": 8, "w": 8, "x": 0, "y": 0}
    assert panels["5xx Ratio"]["gridPos"] == {"h": 8, "w": 8, "x": 8, "y": 0}
    assert panels["P95 Latency"]["gridPos"] == {"h": 8, "w": 8, "x": 16, "y": 0}
    assert panels["Service Status"]["gridPos"] == {"h": 8, "w": 8, "x": 0, "y": 8}
    assert panels["4xx Ratio"]["gridPos"] == {"h": 8, "w": 8, "x": 8, "y": 8}
    assert panels["Latency Percentiles"]["gridPos"] == {"h": 8, "w": 8, "x": 16, "y": 8}
    assert panels["Requests by Route"]["gridPos"] == {"h": 8, "w": 24, "x": 0, "y": 16}

    for panel in panels.values():
        assert panel["datasource"] == {"type": "prometheus", "uid": "prometheus"}

    request_rate = panels["Request Rate"]["targets"][0]["expr"]
    assert request_rate == (
        'sum by (service) '
        '(rate(pawprints_http_requests_total{route!~"^/(healthz|readyz|metrics)$"}[5m]))'
    )
    assert panels["Request Rate"]["fieldConfig"]["defaults"]["unit"] == "reqps"

    expected_ratio_exprs = {
        "5xx Ratio": (
            '(sum by (service) (rate(pawprints_http_requests_total{status_code=~"5..", '
            'route!~"^/(healthz|readyz|metrics)$"}[5m])) / sum by (service) '
            '(rate(pawprints_http_requests_total{route!~"^/(healthz|readyz|metrics)$"}[5m]))) '
            'or on(service) (0 * sum by (service) '
            '(rate(pawprints_http_requests_total{route!~"^/(healthz|readyz|metrics)$"}[5m])))'
        ),
        "4xx Ratio": (
            '(sum by (service) (rate(pawprints_http_requests_total{status_code=~"4..", '
            'route!~"^/(healthz|readyz|metrics)$"}[5m])) / sum by (service) '
            '(rate(pawprints_http_requests_total{route!~"^/(healthz|readyz|metrics)$"}[5m]))) '
            'or on(service) (0 * sum by (service) '
            '(rate(pawprints_http_requests_total{route!~"^/(healthz|readyz|metrics)$"}[5m])))'
        ),
    }
    for title in ("5xx Ratio", "4xx Ratio"):
        expr = panels[title]["targets"][0]["expr"]
        assert expr == expected_ratio_exprs[title]
        assert expr.count(application_route_filter) == 3
        assert "/internal" not in expr
        assert "vector(0)" not in expr
        assert panels[title]["fieldConfig"]["defaults"]["unit"] == "percentunit"
        assert panels[title]["fieldConfig"]["defaults"]["min"] == 0
        assert panels[title]["fieldConfig"]["defaults"]["max"] == 1

    assert panels["P95 Latency"]["targets"][0]["expr"] == (
        "histogram_quantile(0.95, "
        'sum by (service, le) '
        '(rate(pawprints_http_request_duration_seconds_bucket{route!~"^/(healthz|readyz|metrics)$"}[5m])))'
    )
    assert panels["P95 Latency"]["fieldConfig"]["defaults"]["unit"] == "s"

    status_panel = panels["Service Status"]
    assert status_panel["type"] == "stat"
    assert status_panel["targets"][0]["expr"] == (
        'label_replace(up{job="pawprints-services"}, "service", "$1", "instance", "([^:]+):.*")'
    )
    assert status_panel["fieldConfig"]["defaults"]["mappings"] == [
        {
            "options": {
                "0": {"color": "red", "text": "DOWN"},
                "1": {"color": "green", "text": "UP"},
            },
            "type": "value",
        }
    ]

    percentile_targets = panels["Latency Percentiles"]["targets"]
    assert [target["legendFormat"] for target in percentile_targets] == [
        "p50 {{service}}",
        "p95 {{service}}",
        "p99 {{service}}",
    ]
    assert [target["expr"] for target in percentile_targets] == [
        'histogram_quantile(0.50, sum by (service, le) (rate(pawprints_http_request_duration_seconds_bucket{route!~"^/(healthz|readyz|metrics)$"}[5m])))',
        'histogram_quantile(0.95, sum by (service, le) (rate(pawprints_http_request_duration_seconds_bucket{route!~"^/(healthz|readyz|metrics)$"}[5m])))',
        'histogram_quantile(0.99, sum by (service, le) (rate(pawprints_http_request_duration_seconds_bucket{route!~"^/(healthz|readyz|metrics)$"}[5m])))',
    ]
    assert panels["Latency Percentiles"]["fieldConfig"]["defaults"]["unit"] == "s"

    route_expr = panels["Requests by Route"]["targets"][0]["expr"]
    assert route_expr == (
        'sum by (service, route) '
        '(rate(pawprints_http_requests_total{route!~"^/(healthz|readyz|metrics)$"}[5m]))'
    )
    assert panels["Requests by Route"]["targets"][0]["legendFormat"] == "{{service}} {{route}}"
    assert panels["Requests by Route"]["fieldConfig"]["defaults"]["unit"] == "reqps"


def test_grafana_dashboard_queries_use_only_privacy_safe_bounded_labels():
    dashboard = json.loads(
        Path("infra/grafana/dashboards/pawprints-service-overview.json").read_text(encoding="utf-8")
    )
    expressions = "\n".join(
        target["expr"]
        for panel in dashboard["panels"]
        for target in panel.get("targets", [])
    )

    assert "pawprints_http_requests_total" in expressions
    assert "pawprints_http_request_duration_seconds_bucket" in expressions
    assert "up{job=\"pawprints-services\"}" in expressions
    for unsafe_label in [
        "user_id",
        "email",
        "event_id",
        "media_id",
        "request_id",
        "raw_url",
        "query_string",
        "description",
        "token",
        "authorization",
        "cookie",
    ]:
        assert unsafe_label not in expressions.lower()
