from __future__ import annotations

from datetime import date
from pathlib import Path
import re

from demo import seed


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]


class FakeApi:
    def __init__(self) -> None:
        self.paths: list[str] = []
        self.categories: dict[str, dict] = {}
        self.events: dict[str, dict] = {}
        self.media_by_event: dict[str, list[dict]] = {}
        self.uploaded_event_ids: list[str] = []
        self.search_calls: list[str] = []
        self.analytics_calls = 0

    def register_or_login(self) -> seed.Session:
        self.paths.extend(["/api/v1/auth/register", "/api/v1/auth/login"])
        return seed.Session(access_token="token", user_id="demo-user")

    def list_categories(self, token: str) -> list[dict]:
        self.paths.append("/api/v1/categories")
        return list(self.categories.values())

    def create_category(self, token: str, name: str) -> dict:
        self.paths.append("/api/v1/categories")
        item = {"id": f"cat-{len(self.categories) + 1}", "name": name}
        self.categories[name.casefold()] = item
        return item

    def search_events(self, token: str, keyword: str) -> list[dict]:
        self.paths.append(f"/api/v1/events/search?keyword={keyword}")
        self.search_calls.append(keyword)
        return [event for event in self.events.values() if keyword in event["description"]]

    def create_event(self, token: str, payload: dict) -> dict:
        self.paths.append("/api/v1/events")
        event = dict(payload)
        event["id"] = f"event-{len(self.events) + 1}"
        event["local_date"] = payload["local_datetime"].split("T", 1)[0]
        self.events[event["id"]] = event
        return event

    def upload_images(self, token: str, event_id: str, image_path: Path) -> list[dict]:
        self.paths.append(f"/api/v1/media/events/{event_id}")
        self.uploaded_event_ids.append(event_id)
        media = [{"id": f"media-{event_id}", "display_order": 1}]
        self.media_by_event[event_id] = media
        return media

    def list_media(self, token: str, event_id: str) -> list[dict]:
        self.paths.append(f"/api/v1/media/events/{event_id}")
        return self.media_by_event.get(event_id, [])

    def timeline(self, token: str, local_date: str) -> list[dict]:
        self.paths.append(f"/api/v1/events/timeline?date={local_date}")
        return [event for event in self.events.values() if event["local_date"] == local_date]

    def activity_counts(self, token: str, start_date: str, end_date: str) -> dict:
        self.paths.append(f"/api/v1/analytics/activity-counts?start_date={start_date}&end_date={end_date}")
        self.analytics_calls += 1
        counts: dict[str, dict] = {}
        for event in self.events.values():
            if start_date <= event["local_date"] <= end_date:
                item = counts.setdefault(
                    event["category_id"],
                    {"category_id": event["category_id"], "category_name": "Demo", "count": 0},
                )
                item["count"] += 1
        return {"items": list(counts.values())}


def test_seed_is_repeatable_and_does_not_duplicate_demo_rows(tmp_path: Path):
    api = FakeApi()
    image_path = tmp_path / "sample.png"
    image_path.write_bytes(seed.SAMPLE_PNG_BYTES)
    settings = seed.SeedSettings(
        base_url="http://nginx",
        email="demo@example.test",
        password="demo123",
        display_name="Pawprints Demo",
        image_path=image_path,
        anchor_date=date(2026, 9, 13),
    )

    first = seed.run_seed(api, settings)
    second = seed.run_seed(api, settings)

    assert first == seed.SeedSummary(categories_created=5, events_created=10, images_uploaded=3)
    assert second == seed.SeedSummary(categories_created=0, events_created=0, images_uploaded=0)
    assert len(api.categories) == 5
    assert set(api.categories) == {"demo walks", "demo meals", "demo training", "demo vet care", "demo quiet moments"}
    assert len(api.events) == 10
    assert len({event["title"] for event in api.events.values()}) == 10
    assert all(event["timezone"] == "Asia/Taipei" for event in api.events.values())
    assert api.analytics_calls == 2
    assert api.search_calls


def test_seed_anchor_date_is_explicit_and_stable(tmp_path: Path):
    api = FakeApi()
    image_path = tmp_path / "sample.png"
    settings = seed.SeedSettings(
        base_url="http://nginx",
        email="demo@example.test",
        password="demo123",
        display_name="Pawprints Demo",
        image_path=image_path,
        anchor_date=date(2026, 9, 13),
    )

    seed.run_seed(api, settings)

    assert {event["local_date"] for event in api.events.values()} == {
        "2026-08-20",
        "2026-08-26",
        "2026-08-30",
        "2026-09-03",
        "2026-09-06",
        "2026-09-08",
        "2026-09-10",
        "2026-09-11",
        "2026-09-12",
    }


def test_seed_fails_when_analytics_cannot_see_seeded_data(tmp_path: Path):
    api = FakeApi()
    image_path = tmp_path / "sample.png"
    settings = seed.SeedSettings(
        base_url="http://nginx",
        email="demo@example.test",
        password="demo123",
        display_name="Pawprints Demo",
        image_path=image_path,
        anchor_date=date(2026, 9, 13),
    )
    api.activity_counts = lambda token, start_date, end_date: {"items": []}

    try:
        seed.run_seed(api, settings)
    except RuntimeError as exc:
        assert "Analytics did not include all demo Pawprints" in str(exc)
    else:
        raise AssertionError("seed should fail when Analytics cannot see seeded data")


def test_seed_fails_when_analytics_only_has_unrelated_category_counts(tmp_path: Path):
    api = FakeApi()
    image_path = tmp_path / "sample.png"
    settings = seed.SeedSettings(
        base_url="http://nginx",
        email="demo@example.test",
        password="demo123",
        display_name="Pawprints Demo",
        image_path=image_path,
        anchor_date=date(2026, 9, 13),
    )
    api.activity_counts = lambda token, start_date, end_date: {
        "items": [{"category_id": "manual-category", "category_name": "Manual", "count": 99}]
    }

    try:
        seed.run_seed(api, settings)
    except RuntimeError as exc:
        assert "Analytics did not include all demo Pawprints" in str(exc)
    else:
        raise AssertionError("seed should fail when Analytics only reports unrelated categories")


def test_seed_fails_when_search_cannot_see_seeded_data(tmp_path: Path):
    api = FakeApi()
    image_path = tmp_path / "sample.png"
    settings = seed.SeedSettings(
        base_url="http://nginx",
        email="demo@example.test",
        password="demo123",
        display_name="Pawprints Demo",
        image_path=image_path,
        anchor_date=date(2026, 9, 13),
    )
    original_search = api.search_events
    search_calls = 0

    def search_returns_matches_only_before_create(token: str, keyword: str) -> list[dict]:
        nonlocal search_calls
        search_calls += 1
        if search_calls <= len(seed.demo_events(settings.anchor_date)):
            return original_search(token, keyword)
        api.paths.append(f"/api/v1/events/search?keyword={keyword}")
        return []

    api.search_events = search_returns_matches_only_before_create

    try:
        seed.run_seed(api, settings)
    except RuntimeError as exc:
        assert "is missing from Search" in str(exc)
    else:
        raise AssertionError("seed should fail when Search cannot see seeded data")


def test_seed_uses_only_public_nginx_api_paths(tmp_path: Path):
    api = FakeApi()
    image_path = tmp_path / "sample.png"
    image_path.write_bytes(seed.SAMPLE_PNG_BYTES)
    settings = seed.SeedSettings(
        base_url="http://nginx",
        email="demo@example.test",
        password="demo123",
        display_name="Pawprints Demo",
        image_path=image_path,
        anchor_date=date(2026, 9, 13),
    )

    seed.run_seed(api, settings)

    assert api.paths
    assert all(path.startswith("/api/v1/") for path in api.paths)
    assert all(not path.startswith("/internal/") for path in api.paths)


def test_seed_defaults_to_local_demo123_credentials(monkeypatch):
    for name in [
        "PAWPRINTS_BASE_URL",
        "PAWPRINTS_DEMO_EMAIL",
        "PAWPRINTS_DEMO_PASSWORD",
        "PAWPRINTS_DEMO_DISPLAY_NAME",
        "PAWPRINTS_DEMO_IMAGE",
        "PAWPRINTS_DEMO_ANCHOR_DATE",
    ]:
        monkeypatch.delenv(name, raising=False)

    settings = seed.SeedSettings.from_env()

    assert settings.email == "demo@pawprints.local"
    assert settings.password == "demo123"


def test_compose_defines_seed_as_explicit_jobs_profile_service():
    compose = (REPOSITORY_ROOT / "compose.yaml").read_text(encoding="utf-8")

    assert re.search(r"(?m)^  seed:\s*$", compose)
    seed_block = compose.split("  seed:", 1)[1].split("\n  redis-test:", 1)[0]
    assert 'profiles: ["jobs"]' in seed_block
    assert "PAWPRINTS_BASE_URL: http://nginx" in seed_block
    assert "PAWPRINTS_DEMO_PASSWORD: ${PAWPRINTS_DEMO_PASSWORD:-demo123}" in seed_block
    assert "PAWPRINTS_DEMO_ANCHOR_DATE: ${PAWPRINTS_DEMO_ANCHOR_DATE:-2026-09-13}" in seed_block
    assert "./demo:/demo:ro" in seed_block
    assert 'command: ["python", "seed.py"]' in seed_block
    assert "depends_on:" in seed_block
    assert "nginx:" in seed_block
    assert "condition: service_healthy" in seed_block


def test_dev_seed_command_runs_checked_compose_job():
    script = (REPOSITORY_ROOT / "scripts/dev.ps1").read_text(encoding="utf-8")

    assert '"seed" { Invoke-Seed }' in script
    assert re.search(
        r'function Invoke-Seed \{\s*'
        r'Invoke-Checked -FilePath docker -Arguments @\("compose", "--profile", "jobs", "run", "--build", "--rm", "seed"\)\s*'
        r'\}',
        script,
    )
