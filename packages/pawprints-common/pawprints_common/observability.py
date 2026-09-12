from __future__ import annotations

import json
import logging
import time
from uuid import uuid4

from fastapi import FastAPI, Request
from prometheus_client import CollectorRegistry, Counter, Histogram, generate_latest
from starlette.responses import Response

from pawprints_common.request_context import REQUEST_ID_HEADER, current_request_id, reset_current_request_id, set_current_request_id


_logger = logging.getLogger("pawprints.requests")


def _route_template(request: Request) -> str:
    route = request.scope.get("route")
    path = getattr(route, "path", None)
    if isinstance(path, str):
        return path
    return "unmatched"


async def _safe_error_code(response: Response) -> tuple[str, Response]:
    if response.status_code < 400:
        return "none", response
    content_type = response.headers.get("content-type", "")
    if "application/json" not in content_type:
        return "none", response

    body = b""
    async for chunk in response.body_iterator:
        body += chunk

    error_code = "none"
    try:
        payload = json.loads(body.decode("utf-8"))
        code = payload.get("error", {}).get("code")
        if isinstance(code, str) and code.replace("_", "").isalnum():
            error_code = code
    except (UnicodeDecodeError, json.JSONDecodeError, AttributeError):
        error_code = "none"

    return error_code, Response(
        content=body,
        status_code=response.status_code,
        headers=dict(response.headers),
        media_type=response.media_type,
        background=response.background,
    )


def install_request_context_and_metrics(app: FastAPI, service_name: str) -> None:
    registry = CollectorRegistry(auto_describe=True)
    request_counter = Counter(
        "pawprints_http_requests_total",
        "HTTP requests handled by Pawprints services.",
        ("service", "method", "route", "status_code", "error_code"),
        registry=registry,
    )
    request_latency = Histogram(
        "pawprints_http_request_duration_seconds",
        "HTTP request latency for Pawprints services.",
        ("service", "method", "route"),
        registry=registry,
    )

    @app.middleware("http")
    async def request_context_and_metrics(request: Request, call_next):
        request_id = request.headers.get(REQUEST_ID_HEADER) or uuid4().hex
        token = set_current_request_id(request_id)
        route = "unmatched"
        status_code = 500
        error_code = "internal_error"
        started = time.perf_counter()
        try:
            response = await call_next(request)
            route = _route_template(request)
            status_code = response.status_code
            error_code, response = await _safe_error_code(response)
            response.headers[REQUEST_ID_HEADER] = request_id
            return response
        finally:
            latency_seconds = time.perf_counter() - started
            request_counter.labels(
                service_name,
                request.method,
                route,
                str(status_code),
                error_code,
            ).inc()
            request_latency.labels(service_name, request.method, route).observe(latency_seconds)
            _logger.info(
                json.dumps(
                    {
                        "event": "http_request",
                        "request_id": request_id,
                        "service": service_name,
                        "level": "info",
                        "method": request.method,
                        "route": route,
                        "status": status_code,
                        "latency_ms": round(latency_seconds * 1000, 3),
                        "error_code": error_code,
                    },
                    separators=(",", ":"),
                    sort_keys=True,
                )
            )
            reset_current_request_id(token)

    @app.get("/metrics", include_in_schema=False)
    def metrics() -> Response:
        return Response(generate_latest(registry), media_type="text/plain; version=0.0.4; charset=utf-8")
