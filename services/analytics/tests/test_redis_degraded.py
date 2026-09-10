from __future__ import annotations

from datetime import date
from uuid import uuid4

from redis import Redis
from redis.exceptions import RedisError

from conftest import USER_A, bearer, insert_fact


def _seed(event_engine):
    category_id = uuid4()
    insert_fact(event_engine, user_id=USER_A, category_id=category_id, category_name="Running", local_date=date(2026, 9, 1))
    return category_id


def _path() -> str:
    return "/api/v1/analytics/activity-counts?start_date=2026-09-01&end_date=2026-09-30"


def test_redis_connection_failure_falls_back_to_postgres(client, token_a, event_engine, monkeypatch):
    category_id = _seed(event_engine)
    import app.routes as routes

    unavailable = Redis(host="127.0.0.1", port=1, socket_connect_timeout=0.05, socket_timeout=0.05, decode_responses=True)
    monkeypatch.setattr(routes, "get_redis", lambda: unavailable)

    response = client.get(_path(), headers=bearer(token_a))

    assert response.status_code == 200
    assert response.json()["items"] == [
        {"category_id": str(category_id), "category_name": "Running", "count": 1}
    ]


def test_redis_get_failure_falls_back_to_postgres(client, token_a, event_engine, monkeypatch):
    category_id = _seed(event_engine)
    import app.routes as routes

    def fail_get(*args, **kwargs):
        raise RedisError("get failed")

    monkeypatch.setattr(routes, "get_cached_result", fail_get)
    response = client.get(_path(), headers=bearer(token_a))

    assert response.status_code == 200
    assert response.json()["items"][0]["category_id"] == str(category_id)


def test_invalid_cache_version_falls_back_to_postgres(client, token_a, event_engine, redis_client):
    category_id = _seed(event_engine)
    redis_client.set(f"analytics:user:{USER_A}:version", "invalid")

    response = client.get(_path(), headers=bearer(token_a))

    assert response.status_code == 200
    assert response.json()["items"][0]["category_id"] == str(category_id)


def test_invalid_cached_payload_falls_back_without_exposing_fields(
    client, token_a, event_engine, monkeypatch
):
    category_id = _seed(event_engine)
    import app.routes as routes

    monkeypatch.setattr(
        routes,
        "get_cached_result",
        lambda *args, **kwargs: {
            "start_date": "2026-09-01",
            "end_date": "2026-09-30",
            "grouping": "none",
            "items": [],
            "user_id": str(USER_A),
        },
    )

    response = client.get(_path(), headers=bearer(token_a))

    assert response.status_code == 200
    assert response.json()["items"][0]["category_id"] == str(category_id)
    assert "user_id" not in response.json()


def test_redis_set_failure_does_not_fail_postgres_result(client, token_a, event_engine, monkeypatch):
    category_id = _seed(event_engine)
    import app.routes as routes

    def fail_set(*args, **kwargs):
        raise RedisError("set failed")

    monkeypatch.setattr(routes, "set_cached_result", fail_set)
    response = client.get(_path(), headers=bearer(token_a))

    assert response.status_code == 200
    assert response.json()["items"][0]["category_id"] == str(category_id)
