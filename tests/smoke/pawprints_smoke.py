from __future__ import annotations

import json
import os
import time
from base64 import b64decode
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
        body: bytes | None = None,
        headers: dict[str, str] | None = None,
        expected: int | tuple[int, ...] = 200,
        decode: bool = True,
    ) -> tuple[int, dict[str, str], str | bytes]:
        request_body = body
        request_headers = {
            "Accept": "application/json",
            "X-Request-Id": f"smoke-{int(time.time() * 1000)}",
        }
        if headers:
            request_headers.update(headers)
        if token:
            request_headers["Authorization"] = f"Bearer {token}"
        if payload is not None:
            request_body = json.dumps(payload).encode("utf-8")
            request_headers["Content-Type"] = "application/json"

        request = Request(f"{self.base_url}{path}", data=request_body, headers=request_headers, method=method)
        expected_statuses = (expected,) if isinstance(expected, int) else expected
        try:
            with self.opener.open(request, timeout=10) as response:
                status = response.status
                response_headers = dict(response.headers.items())
                response_body = response.read()
        except HTTPError as exc:
            status = exc.code
            response_headers = dict(exc.headers.items())
            response_body = exc.read()
        except URLError as exc:
            raise AssertionError(f"{method} {path} failed to connect to {self.base_url}: {exc}") from exc

        result: str | bytes = response_body.decode("utf-8") if decode else response_body
        if status not in expected_statuses:
            raise AssertionError(f"{method} {path} returned {status}, expected {expected_statuses}: {result}")
        return status, response_headers, result

    def json_request(self, method: str, path: str, **kwargs) -> tuple[int, dict[str, str], dict]:
        status, headers, text = self.request(method, path, **kwargs)
        try:
            assert isinstance(text, str)
            return status, headers, json.loads(text)
        except json.JSONDecodeError as exc:
            raise AssertionError(f"{method} {path} returned invalid JSON: {text}") from exc


def small_png() -> bytes:
    return b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAIAAACQd1PeAAAADUlEQVR4nGNMmXaCAQAEpwIWeLwOZAAAAABJRU5ErkJggg==")


def header_value(headers: dict[str, str], name: str) -> str | None:
    normalized_name = name.casefold()
    return next((value for key, value in headers.items() if key.casefold() == normalized_name), None)


def small_jpeg() -> bytes:
    return b64decode("/9j/4AAQSkZJRgABAQAAAQABAAD/2wBDAAgGBgcGBQgHBwcJCQgKDBQNDAsLDBkSEw8UHRofHh0aHBwgJC4nICIsIxwcKDcpLDAxNDQ0Hyc5PTgyPC4zNDL/2wBDAQkJCQwLDBgNDRgyIRwhMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjL/wAARCAAMAAwDASIAAhEBAxEB/8QAHwAAAQUBAQEBAQEAAAAAAAAAAAECAwQFBgcICQoL/8QAtRAAAgEDAwIEAwUFBAQAAAF9AQIDAAQRBRIhMUEGE1FhByJxFDKBkaEII0KxwRVS0fAkM2JyggkKFhcYGRolJicoKSo0NTY3ODk6Q0RFRkdISUpTVFVWV1hZWmNkZWZnaGlqc3R1dnd4eXqDhIWGh4iJipKTlJWWl5iZmqKjpKWmp6ipqrKztLW2t7i5usLDxMXGx8jJytLT1NXW19jZ2uHi4+Tl5ufo6erx8vP09fb3+Pn6/8QAHwEAAwEBAQEBAQEBAQAAAAAAAAECAwQFBgcICQoL/8QAtREAAgECBAQDBAcFBAQAAQJ3AAECAxEEBSExBhJBUQdhcRMiMoEIFEKRobHBCSMzUvAVYnLRChYkNOEl8RcYGRomJygpKjU2Nzg5OkNERUZHSElKU1RVVldYWVpjZGVmZ2hpanN0dXZ3eHl6goOEhYaHiImKkpOUlZaXmJmaoqOkpaanqKmqsrO0tba3uLm6wsPExcbHyMnK0tPU1dbX2Nna4uPk5ebn6Onq8vP09fb3+Pn6/9oADAMBAAIRAxEAPwDxGiiitjI//9k=")


def multipart_images(images: list[bytes]) -> tuple[bytes, str]:
    boundary = f"pawprints-smoke-{int(time.time() * 1000)}"
    chunks: list[bytes] = []
    mime_types = ["image/png", "image/jpeg"]
    filenames = ["smoke.png", "smoke.jpg"]
    for index, image in enumerate(images):
        chunks.extend(
            [
                f"--{boundary}\r\n".encode("ascii"),
                (
                    'Content-Disposition: form-data; name="files"; '
                    f'filename="{filenames[index % len(filenames)]}"\r\n'
                ).encode("ascii"),
                f"Content-Type: {mime_types[index % len(mime_types)]}\r\n\r\n".encode("ascii"),
                image,
                b"\r\n",
            ]
        )
    chunks.append(f"--{boundary}--\r\n".encode("ascii"))
    return b"".join(chunks), f"multipart/form-data; boundary={boundary}"


def upload_images(client: SmokeClient, token: str, event_id: str, images: list[bytes]) -> list[dict]:
    body, content_type = multipart_images(images)
    _, _, created = client.json_request(
        "POST",
        f"/api/v1/media/events/{event_id}",
        token=token,
        body=body,
        headers={"Content-Type": content_type},
        expected=201,
    )
    assert isinstance(created, list), "media upload did not return a list"
    return created


def list_media(client: SmokeClient, token: str, event_id: str) -> list[dict]:
    _, _, listed = client.json_request("GET", f"/api/v1/media/events/{event_id}", token=token)
    assert isinstance(listed, list), "media list did not return a list"
    return listed


def fetch_media_bytes(client: SmokeClient, token: str, media_id: str) -> bytes:
    _, _, body = client.request(
        "GET",
        f"/api/v1/media/{media_id}",
        token=token,
        headers={"Accept": "image/*"},
        decode=False,
    )
    assert isinstance(body, bytes)
    return body


def unique_email() -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S%f")
    return f"smoke-{stamp}@example.test"


def main() -> None:
    client = SmokeClient(BASE_URL)

    _, _, home = client.request("GET", "/", expected=200)
    assert "Pawprints" in home, "React shell did not render Pawprints"
    client.request("GET", "/metrics", expected=404)

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
    _, _, second_category = client.json_request(
        "POST",
        "/api/v1/categories",
        token=token,
        payload={"name": f"Smoke Reading {int(time.time())}"},
        expected=201,
    )
    second_category_id = second_category["id"]

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
    event_etag = header_value(event_headers, "ETag")
    assert event_etag, "created event did not return an ETag"
    assert event["title"] == "Smoke Pawprint"

    client.json_request(
        "POST",
        "/api/v1/events",
        token=token,
        payload={
            "title": "Second Smoke Pawprint",
            "category_id": category_id,
            "local_datetime": f"{event_date}T18:00:00",
            "timezone": "Asia/Taipei",
        },
        expected=201,
    )
    client.json_request(
        "POST",
        "/api/v1/events",
        token=token,
        payload={
            "title": "Smoke Reading Pawprint",
            "category_id": second_category_id,
            "local_datetime": f"{event_date}T20:00:00",
            "timezone": "Asia/Taipei",
        },
        expected=201,
    )

    analytics_query = urlencode({"start_date": event_date, "end_date": event_date})
    analytics_path = f"/api/v1/analytics/activity-counts?{analytics_query}"
    client.request("GET", analytics_path, expected=401)
    _, _, activity_counts = client.json_request("GET", analytics_path, token=token)
    counts_by_category = {item["category_id"]: item["count"] for item in activity_counts["items"]}
    assert counts_by_category[category_id] == 2, "Analytics did not count both real Event rows"
    assert counts_by_category[second_category_id] == 1, "Analytics did not isolate category totals"
    client.request(
        "POST",
        f"/internal/analytics/users/{event_id}/invalidate",
        headers={
            "X-User-Id": "spoofed",
            "X-Pawprints-Internal-Service": "event",
            "X-Pawprints-Internal-Token": "spoofed",
        },
        expected=404,
    )

    _, _, categories = client.json_request("GET", "/api/v1/categories", token=token)
    assert any(item["id"] == category_id for item in categories["items"]), "category collection did not include created category"

    query = urlencode({"date": event_date})
    _, _, timeline = client.json_request("GET", f"/api/v1/events/timeline?{query}", token=token)
    assert any(item["id"] == event_id for item in timeline["items"]), "timeline did not include created event"

    _, _, fetched = client.json_request("GET", f"/api/v1/events/{event_id}", token=token)
    assert fetched["id"] == event_id, "nested event route did not return created event"

    media = upload_images(client, token, event_id, [small_png(), small_jpeg()])
    assert [item["display_order"] for item in media] == [1, 2], "media upload did not preserve batch display order"
    listed = list_media(client, token, event_id)
    assert [item["id"] for item in listed] == [item["id"] for item in media], "media list did not match uploaded media"
    image = fetch_media_bytes(client, token, media[0]["id"])
    assert image.startswith(b"\x89PNG") or image.startswith(b"\xff\xd8"), "media retrieval did not stream image bytes"
    client.request("GET", f"/api/v1/media/{media[0]['id']}", expected=404)
    client.request(
        "POST",
        f"/internal/media/events/{event_id}/cleanup",
        token=token,
        headers={
            "X-User-Id": "spoofed",
            "X-Pawprints-Internal-Service": "event",
            "X-Pawprints-Internal-Token": "spoofed",
        },
        expected=(404, 401, 403),
    )

    _, _, search = client.json_request("GET", "/api/v1/events/search?keyword=Smoke+Pawprint", token=token)
    assert any(item["id"] == event_id for item in search["items"]), "collection search route did not include created event"

    _, patched_headers, patched = client.json_request(
        "PATCH",
        f"/api/v1/events/{event_id}?source=smoke",
        token=token,
        headers={"If-Match": event_etag},
        payload={"mood": "great"},
    )
    assert patched["mood"] == "great", "nested event route did not preserve method, URI, or query"
    patched_etag = header_value(patched_headers, "ETag")
    assert patched_etag, "patched event did not return an ETag"

    _, _, counts_after_patch = client.json_request("GET", analytics_path, token=token)
    cached_counts = {item["category_id"]: item["count"] for item in counts_after_patch["items"]}
    assert cached_counts[category_id] == 2, "Analytics did not retain both events after patch"

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

    client.request(
        "DELETE",
        f"/api/v1/events/{event_id}",
        token=token,
        headers={"If-Match": patched_etag},
        expected=204,
    )
    client.request("GET", f"/api/v1/events/{event_id}", token=token, expected=404)

    _, _, timeline_after_delete = client.json_request("GET", f"/api/v1/events/timeline?{query}", token=token)
    assert all(item["id"] != event_id for item in timeline_after_delete["items"]), "timeline retained deleted event"

    _, _, search_after_delete = client.json_request(
        "GET", "/api/v1/events/search?keyword=Smoke+Pawprint", token=token
    )
    assert all(item["id"] != event_id for item in search_after_delete["items"]), "search retained deleted event"

    client.request("GET", f"/api/v1/media/events/{event_id}", token=token, expected=404)
    for item in media:
        client.request("GET", f"/api/v1/media/{item['id']}", token=token, expected=404)

    _, _, counts_after_delete = client.json_request("GET", analytics_path, token=token)
    updated_counts = {item["category_id"]: item["count"] for item in counts_after_delete["items"]}
    assert updated_counts[category_id] == 1, "Analytics retained deleted event"

    print("Pawprints public-boundary smoke passed.")


if __name__ == "__main__":
    main()
