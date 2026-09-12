from __future__ import annotations

import re
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
NGINX_CONF = REPOSITORY_ROOT / "infra/nginx/nginx.conf"
COMPOSE_YAML = REPOSITORY_ROOT / "compose.yaml"

PUBLIC_PROXY_PREFIXES = (
    "/api/v1/auth",
    "/api/v1/categories",
    "/api/v1/events",
    "/api/v1/media",
    "/api/v1/analytics",
)
PRIVATE_SERVICES = ("auth", "event", "media", "analytics")
LOCAL_DEMO_PORT_SERVICES = ("nginx", "prometheus", "grafana")


def _location_block(conf: str, matcher: str) -> str:
    pattern = re.compile(rf"location\s+{re.escape(matcher)}\s*\{{(?P<body>.*?)\n    \}}", re.DOTALL)
    match = pattern.search(conf)
    assert match is not None, f"Missing Nginx location {matcher}"
    return match.group("body")


def _service_block(compose: str, service_name: str) -> str:
    lines = compose.splitlines()
    body = []
    in_service = False
    for line in lines:
        if line == f"  {service_name}:":
            in_service = True
            continue
        if in_service and line.startswith("  ") and not line.startswith("    "):
            break
        if in_service:
            body.append(line)
    assert in_service, f"Missing Compose service {service_name}"
    return "\n".join(body)


def test_nginx_public_proxy_strips_spoofable_internal_headers_and_owns_request_id():
    conf = NGINX_CONF.read_text(encoding="utf-8")

    assert "add_header X-Request-Id $request_id always;" in conf
    assert "proxy_set_header X-Request-Id $request_id;" in conf
    assert "proxy_set_header X-Request-Id $http_x_request_id;" not in conf

    for prefix in PUBLIC_PROXY_PREFIXES:
        for matcher in (f"= {prefix}", f"{prefix}/"):
            block = _location_block(conf, matcher)
            assert "proxy_set_header Authorization $http_authorization;" in block
            assert "proxy_set_header Cookie $http_cookie;" in block
            assert "proxy_set_header X-Forwarded-For $remote_addr;" in block
            assert "$proxy_add_x_forwarded_for" not in block
            assert 'proxy_set_header X-User-Id "";' in block
            assert 'proxy_set_header X-Pawprints-Internal-Service "";' in block
            assert 'proxy_set_header X-Pawprints-Internal-Token "";' in block


def test_nginx_does_not_expose_internal_or_metrics_routes_publicly():
    conf = NGINX_CONF.read_text(encoding="utf-8")

    assert "location /internal/" in conf
    assert re.search(r"location\s+/internal/\s*\{\s*return 404;", conf, re.DOTALL)
    assert re.search(r"location\s+=\s+/metrics\s*\{\s*return 404;", conf, re.DOTALL)
    assert "proxy_pass http://prometheus" not in conf
    assert "proxy_pass http://grafana" not in conf


def test_private_backend_services_do_not_publish_host_ports():
    compose = COMPOSE_YAML.read_text(encoding="utf-8")

    for service in PRIVATE_SERVICES:
        block = _service_block(compose, service)
        assert re.search(r"(?m)^    ports:\s*$", block) is None, f"{service} exposes host ports"


def test_demo_only_public_ports_are_bound_to_loopback():
    compose = COMPOSE_YAML.read_text(encoding="utf-8")

    for service in LOCAL_DEMO_PORT_SERVICES:
        block = _service_block(compose, service)
        ports_match = re.search(r"(?m)^    ports:\s*\n(?P<ports>(?:      - .*\n?)+)", block)
        assert ports_match is not None, f"{service} should declare an explicit local demo port"
        port_lines = re.findall(r'(?m)^      - "([^"]+)"\s*$', ports_match.group("ports"))
        assert port_lines, f"{service} should declare an explicit local demo port"
        assert all(line.startswith("127.0.0.1:") for line in port_lines)


def test_nginx_access_log_format_omits_query_strings_and_raw_request_target():
    conf = NGINX_CONF.read_text(encoding="utf-8")

    assert "access_log /var/log/nginx/access.log pawprints;" in conf
    assert "log_format pawprints" in conf
    log_format = conf.split("log_format pawprints", 1)[1].split(";", 1)[0]

    assert "$request_method" in log_format
    assert "$uri" in log_format
    assert "$request_id" in log_format
    assert "$request_uri" not in log_format
    assert "$args" not in log_format
    assert "$query_string" not in log_format
    assert "$request " not in log_format
    assert "$http_referer" not in log_format
