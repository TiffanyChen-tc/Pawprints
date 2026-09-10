from __future__ import annotations

import json
import os
import time
from datetime import datetime, timezone
from http.cookiejar import CookieJar
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import HTTPCookieProcessor, Request, build_opener


BASE_URL = os.environ.get("PAWPRINTS_BASE_URL", "http://nginx").rstrip("/")


class SmokeClient:
    def __init__(self, base_url: str) -> None:
        self.base_url = base_url
        self.opener = build_opener(HTTPCookieProcessor(CookieJar()))

    def request(
        self,
        method: str,
        path: str,
        *,
        token: str | None = None,
        payload: dict | None = None,
        headers: dict[str, str] | None = None,
        expected: int | tuple[int, ...] = 200,
    ) -> tuple[int, dict[str, str], str]:
        body = None
        request_headers = {
            "Accept": "application/json",
            "X-Request-Id": f"smoke-{int(time.time() * 1000)}",
        }
        if headers:
            request_headers.update(headers)
        if token:
            request_headers["Authorization"] = f"Bearer {token}"
        if payload is not None:
            body = json.dumps(payload).encode("utf-8")
            request_headers["Content-Type"] = "application/json"

        request = Request(f"{self.base_url}{path}", data=body, headers=request_headers, method=method)
        expected_statuses = (expected,) if isinstance(expected, int) else expected
        try:
            with self.opener.open(request, timeout=10) as response:
                status = response.status
                response_headers = dict(response.headers.items())
                text = response.read().decode("utf-8")
        except HTTPError as exc:
            status = exc.code
            response_headers = dict(exc.headers.items())
            text = exc.read().decode("utf-8")
        except URLError as exc:
            raise AssertionError(f"{method} {path} failed to connect to {self.base_url}: {exc}") from exc

        if status not in expected_statuses:
            raise AssertionError(f"{method} {path} returned {status}, expected {expected_statuses}: {text}")
        return status, response_headers, text

    def json_request(self, method: str, path: str, **kwargs) -> tuple[int, dict[str, str], dict]:
        status, headers, text = self.request(method, path, **kwargs)
        try:
            return status, headers, json.loads(text)
        except json.JSONDecodeError as exc:
            raise AssertionError(f"{method} {path} returned invalid JSON: {text}") from exc


def unique_email() -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S%f")
    return f"smoke-{stamp}@example.test"


def main() -> None:
    client = SmokeClient(BASE_URL)

    _, _, home = client.request("GET", "/", expected=200)
    assert "Pawprints" in home, "React shell did not render Pawprints"

    _, _, session = client.json_request(
        "POST",
        "/api/v1/auth/register",
        payload={
            "email": unique_email(),
            "password": "CorrectHorseBatteryStaple1!",
            "display_name": "Smoke Tester",
        },
        expected=201,
    )
    token = session["access_token"]

    _, _, category = client.json_request(
        "POST",
        "/api/v1/categories",
        token=token,
        payload={"name": f"Smoke Category {int(time.time())}"},
        expected=201,
    )
    category_id = category["id"]

    event_date = "2026-09-10"
    _, event_headers, event = client.json_request(
        "POST",
        "/api/v1/events",
        token=token,
        payload={
            "title": "Smoke Pawprint",
            "category_id": category_id,
            "local_datetime": f"{event_date}T09:30:00",
            "timezone": "Asia/Taipei",
            "description": "Created by Task 5 smoke.",
            "mood": "good",
            "location_name": "Pawprints smoke",
            "latitude": 25.0330,
            "longitude": 121.5654,
        },
        expected=201,
    )
    event_id = event["id"]
    event_etag = event_headers.get("ETag")
    assert event["title"] == "Smoke Pawprint"

    _, _, categories = client.json_request("GET", "/api/v1/categories", token=token)
    assert any(item["id"] == category_id for item in categories["items"]), "category collection did not include created category"

    query = urlencode({"date": event_date})
    _, _, timeline = client.json_request("GET", f"/api/v1/events/timeline?{query}", token=token)
    assert any(item["id"] == event_id for item in timeline["items"]), "timeline did not include created event"

    _, _, fetched = client.json_request("GET", f"/api/v1/events/{event_id}", token=token)
    assert fetched["id"] == event_id, "nested event route did not return created event"

    _, _, search = client.json_request("GET", "/api/v1/events/search?keyword=Smoke+Pawprint", token=token)
    assert any(item["id"] == event_id for item in search["items"]), "collection search route did not include created event"

    if event_etag:
        _, _, patched = client.json_request(
            "PATCH",
            f"/api/v1/events/{event_id}?source=smoke",
            token=token,
            headers={"If-Match": event_etag},
            payload={"mood": "great"},
        )
        assert patched["mood"] == "great", "nested event route did not preserve method, URI, or query"

    client.request(
        "GET",
        f"/internal/events/{event_id}/ownership",
        token=token,
        headers={
            "X-User-Id": "spoofed",
            "X-Pawprints-Internal-Service": "media",
            "X-Pawprints-Internal-Token": "spoofed",
        },
        expected=(404, 401, 403),
    )

    print("Pawprints public-boundary smoke passed.")


if __name__ == "__main__":
    main()
