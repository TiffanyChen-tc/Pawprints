from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
import json
import os
from pathlib import Path
import time
from base64 import b64decode
from http.cookiejar import CookieJar
from typing import Protocol
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import HTTPCookieProcessor, Request, build_opener


SAMPLE_PNG_BYTES = b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAIAAACQd1PeAAAADUlEQVR4nGNMmXaCAQAEpwIWeLwOZAAAAABJRU5ErkJggg=="
)
DEMO_MARKER_PREFIX = "pawprints-demo-seed:v2"


@dataclass(frozen=True)
class Session:
    access_token: str
    user_id: str


@dataclass(frozen=True)
class SeedSummary:
    categories_created: int
    events_created: int
    images_uploaded: int


@dataclass(frozen=True)
class SeedSettings:
    base_url: str
    email: str
    password: str
    display_name: str
    image_path: Path
    anchor_date: date

    @classmethod
    def from_env(cls) -> SeedSettings:
        default_image = Path(__file__).resolve().parent / "assets" / "sample.png"
        return cls(
            base_url=os.environ.get("PAWPRINTS_BASE_URL", "http://localhost:8080").rstrip("/"),
            email=os.environ.get("PAWPRINTS_DEMO_EMAIL", "demo@pawprints.local"),
            password=os.environ.get("PAWPRINTS_DEMO_PASSWORD", "demo123"),
            display_name=os.environ.get("PAWPRINTS_DEMO_DISPLAY_NAME", "Pawprints Demo"),
            image_path=Path(os.environ.get("PAWPRINTS_DEMO_IMAGE", str(default_image))),
            anchor_date=date.fromisoformat(os.environ.get("PAWPRINTS_DEMO_ANCHOR_DATE", "2026-09-13")),
        )


class SeedApi(Protocol):
    def register_or_login(self) -> Session: ...
    def list_categories(self, token: str) -> list[dict]: ...
    def create_category(self, token: str, name: str) -> dict: ...
    def search_events(self, token: str, keyword: str) -> list[dict]: ...
    def create_event(self, token: str, payload: dict) -> dict: ...
    def list_media(self, token: str, event_id: str) -> list[dict]: ...
    def upload_images(self, token: str, event_id: str, image_path: Path) -> list[dict]: ...
    def timeline(self, token: str, local_date: str) -> list[dict]: ...
    def activity_counts(self, token: str, start_date: str, end_date: str) -> dict: ...


class HttpSeedApi:
    def __init__(self, settings: SeedSettings) -> None:
        self.settings = settings
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
    ) -> tuple[int, dict[str, str], bytes]:
        request_body = body
        request_headers = {
            "Accept": "application/json",
            "X-Request-Id": f"seed-{int(time.time() * 1000)}",
        }
        if headers:
            request_headers.update(headers)
        if token:
            request_headers["Authorization"] = f"Bearer {token}"
        if payload is not None:
            request_body = json.dumps(payload).encode("utf-8")
            request_headers["Content-Type"] = "application/json"

        request = Request(
            f"{self.settings.base_url}{path}",
            data=request_body,
            headers=request_headers,
            method=method,
        )
        expected_statuses = (expected,) if isinstance(expected, int) else expected
        try:
            with self.opener.open(request, timeout=15) as response:
                status = response.status
                response_headers = dict(response.headers.items())
                response_body = response.read()
        except HTTPError as exc:
            status = exc.code
            response_headers = dict(exc.headers.items())
            response_body = exc.read()
        except URLError as exc:
            raise RuntimeError(f"{method} {path} failed to connect to {self.settings.base_url}: {exc}") from exc

        if status not in expected_statuses:
            text = response_body.decode("utf-8", errors="replace")
            raise RuntimeError(f"{method} {path} returned {status}, expected {expected_statuses}: {text}")
        return status, response_headers, response_body

    def json_request(self, method: str, path: str, **kwargs) -> tuple[int, dict[str, str], dict | list]:
        status, headers, body = self.request(method, path, **kwargs)
        return status, headers, json.loads(body.decode("utf-8"))

    def register_or_login(self) -> Session:
        payload = {
            "email": self.settings.email,
            "password": self.settings.password,
            "display_name": self.settings.display_name,
        }
        status, _, body = self.request("POST", "/api/v1/auth/register", payload=payload, expected=(201, 409))
        if status == 409:
            _, _, session = self.json_request(
                "POST",
                "/api/v1/auth/login",
                payload={"email": self.settings.email, "password": self.settings.password},
            )
        else:
            session = json.loads(body.decode("utf-8"))
        return Session(access_token=session["access_token"], user_id=session["user"]["id"])

    def list_categories(self, token: str) -> list[dict]:
        _, _, body = self.json_request("GET", "/api/v1/categories", token=token)
        return body["items"]

    def create_category(self, token: str, name: str) -> dict:
        _, _, body = self.json_request("POST", "/api/v1/categories", token=token, payload={"name": name}, expected=201)
        return body

    def search_events(self, token: str, keyword: str) -> list[dict]:
        _, _, body = self.json_request("GET", f"/api/v1/events/search?{urlencode({'keyword': keyword})}", token=token)
        return body["items"]

    def create_event(self, token: str, payload: dict) -> dict:
        _, _, body = self.json_request("POST", "/api/v1/events", token=token, payload=payload, expected=201)
        return body

    def list_media(self, token: str, event_id: str) -> list[dict]:
        _, _, body = self.json_request("GET", f"/api/v1/media/events/{event_id}", token=token)
        return body

    def upload_images(self, token: str, event_id: str, image_path: Path) -> list[dict]:
        boundary = f"pawprints-seed-{int(time.time() * 1000)}"
        image_bytes = image_path.read_bytes()
        body = b"".join(
            [
                f"--{boundary}\r\n".encode("ascii"),
                b'Content-Disposition: form-data; name="files"; filename="demo-sample.png"\r\n',
                b"Content-Type: image/png\r\n\r\n",
                image_bytes,
                b"\r\n",
                f"--{boundary}--\r\n".encode("ascii"),
            ]
        )
        _, _, response_body = self.json_request(
            "POST",
            f"/api/v1/media/events/{event_id}",
            token=token,
            body=body,
            headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
            expected=201,
        )
        return response_body

    def timeline(self, token: str, local_date: str) -> list[dict]:
        _, _, body = self.json_request("GET", f"/api/v1/events/timeline?{urlencode({'date': local_date})}", token=token)
        return body["items"]

    def activity_counts(self, token: str, start_date: str, end_date: str) -> dict:
        query = urlencode({"start_date": start_date, "end_date": end_date})
        _, _, body = self.json_request("GET", f"/api/v1/analytics/activity-counts?{query}", token=token)
        return body


def demo_categories() -> list[str]:
    return ["Demo Walks", "Demo Meals", "Demo Training", "Demo Vet Care", "Demo Quiet Moments"]


def demo_events(today: date) -> list[dict[str, str]]:
    specs = [
        (-1, "08:10", "Morning park loop", "Demo Walks", "great", "Riverside Park"),
        (-1, "18:25", "Dinner and puzzle feeder", "Demo Meals", "good", "Kitchen"),
        (-2, "07:45", "Loose-leash practice", "Demo Training", "good", "Neighborhood"),
        (-3, "12:30", "Vet check-in notes", "Demo Vet Care", "neutral", "Clinic"),
        (-5, "21:00", "Rainy window watch", "Demo Quiet Moments", "neutral", "Living room"),
        (-7, "09:20", "Trail sniff safari", "Demo Walks", "great", "Forest trail"),
        (-10, "17:40", "New recall cue", "Demo Training", "good", "Backyard"),
        (-14, "08:35", "Breakfast appetite normal", "Demo Meals", "good", "Kitchen"),
        (-18, "16:10", "Nail trim recovery", "Demo Vet Care", "low", "Grooming mat"),
        (-24, "20:05", "Couch nap after visitors", "Demo Quiet Moments", "great", "Living room"),
    ]
    events = []
    for index, (offset, clock, title, category, mood, location) in enumerate(specs, start=1):
        local_date = today + timedelta(days=offset)
        slug = f"event-{index:02d}"
        events.append(
            {
                "slug": slug,
                "title": title,
                "category": category,
                "local_datetime": f"{local_date.isoformat()}T{clock}:00",
                "timezone": "Asia/Taipei",
                "description": f"{DEMO_MARKER_PREFIX}:{slug}\n\nA synthetic demo Pawprint for local walkthroughs.",
                "mood": mood,
                "location_name": location,
            }
        )
    return events


def ensure_categories(api: SeedApi, token: str) -> tuple[dict[str, dict], int]:
    existing = {item["name"].casefold(): item for item in api.list_categories(token)}
    created = 0
    for name in demo_categories():
        if name.casefold() not in existing:
            existing[name.casefold()] = api.create_category(token, name)
            created += 1
    return existing, created


def ensure_events(api: SeedApi, token: str, categories: dict[str, dict], anchor_date: date) -> tuple[list[dict], int]:
    created_events: list[dict] = []
    created_count = 0
    for event_spec in demo_events(anchor_date):
        marker = f"{DEMO_MARKER_PREFIX}:{event_spec['slug']}"
        matches = api.search_events(token, marker)
        if matches:
            created_events.append(matches[0])
            continue
        payload = {
            "title": event_spec["title"],
            "category_id": categories[event_spec["category"].casefold()]["id"],
            "local_datetime": event_spec["local_datetime"],
            "timezone": event_spec["timezone"],
            "description": event_spec["description"],
            "mood": event_spec["mood"],
            "location_name": event_spec["location_name"],
        }
        created_events.append(api.create_event(token, payload))
        created_count += 1
    return created_events, created_count


def verify_visible_seed_data(api: SeedApi, token: str, events: list[dict]) -> None:
    for event in events:
        marker = event["description"].splitlines()[0]
        matches = api.search_events(token, marker)
        if event["id"] not in {match["id"] for match in matches}:
            raise RuntimeError(f"seed verification failed: {event['title']} is missing from Search")

    timeline_date = events[0]["local_date"]
    timeline_ids = {event["id"] for event in api.timeline(token, timeline_date)}
    if events[0]["id"] not in timeline_ids:
        raise RuntimeError("seed verification failed: newest demo Pawprint is missing from Timeline")

    date_values = sorted(event["local_date"] for event in events)
    counts = api.activity_counts(token, date_values[0], date_values[-1])
    expected_by_category: dict[str, int] = {}
    for event in events:
        expected_by_category[event["category_id"]] = expected_by_category.get(event["category_id"], 0) + 1
    actual_by_category = {item["category_id"]: item["count"] for item in counts.get("items", [])}
    for category_id, expected_count in expected_by_category.items():
        if actual_by_category.get(category_id, 0) < expected_count:
            raise RuntimeError("seed verification failed: Analytics did not include all demo Pawprints")


def run_seed(api: SeedApi, settings: SeedSettings) -> SeedSummary:
    session = api.register_or_login()
    categories, categories_created = ensure_categories(api, session.access_token)
    events, events_created = ensure_events(api, session.access_token, categories, settings.anchor_date)

    images_uploaded = 0
    if settings.image_path.exists():
        for event in events[:3]:
            if not api.list_media(session.access_token, event["id"]):
                images_uploaded += len(api.upload_images(session.access_token, event["id"], settings.image_path))

    verify_visible_seed_data(api, session.access_token, events)
    return SeedSummary(categories_created, events_created, images_uploaded)


def main() -> None:
    settings = SeedSettings.from_env()
    summary = run_seed(HttpSeedApi(settings), settings)
    print(
        "Pawprints demo seed complete: "
        f"{summary.categories_created} categories created, "
        f"{summary.events_created} events created, "
        f"{summary.images_uploaded} images uploaded."
    )


if __name__ == "__main__":
    main()
