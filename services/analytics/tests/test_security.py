from __future__ import annotations

from uuid import uuid4

import pytest
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import DBAPIError

from conftest import USER_A


def test_analytics_role_can_select_only_approved_view_columns(analytics_database_url):
    engine = create_engine(analytics_database_url)
    with engine.connect() as connection:
        row = connection.execute(
            text(
                "SELECT event_id, user_id, category_id, category_name, local_date "
                "FROM events.analytics_event_facts LIMIT 1"
            )
        ).first()
        columns = {
            column["name"]
            for column in inspect(connection).get_columns("analytics_event_facts", schema="events")
        }
    engine.dispose()
    assert row is None
    assert columns == {"event_id", "user_id", "category_id", "category_name", "local_date"}


@pytest.mark.parametrize("table", ["events", "categories"])
def test_analytics_role_cannot_select_event_base_tables(analytics_database_url, table):
    engine = create_engine(analytics_database_url)
    with engine.connect() as connection:
        with pytest.raises(DBAPIError, match="permission denied"):
            connection.execute(text(f"SELECT count(*) FROM events.{table}")).scalar_one()
    engine.dispose()


@pytest.mark.parametrize(
    "statement",
    [
        "INSERT INTO events.categories (id, user_id, name, normalized_name, version, created_at, updated_at) "
        "VALUES (:id, :user_id, 'Blocked', 'blocked', 1, now(), now())",
        "UPDATE events.events SET title = title WHERE false",
        "DELETE FROM events.events WHERE false",
    ],
)
def test_analytics_role_cannot_mutate_event_base_data(analytics_database_url, statement):
    engine = create_engine(analytics_database_url)
    with engine.connect() as connection:
        with pytest.raises(DBAPIError, match="permission denied"):
            connection.execute(text(statement), {"id": uuid4(), "user_id": USER_A})
    engine.dispose()


def test_internal_invalidation_allows_only_event_and_is_repeatable(client, redis_client):
    from app.cache import get_user_cache_version

    path = f"/internal/analytics/users/{USER_A}/invalidate"
    before = get_user_cache_version(redis_client, USER_A)

    first = client.post(
        path,
        headers={"X-Pawprints-Internal-Service": "event", "X-Pawprints-Internal-Token": "event-secret"},
    )
    second = client.post(
        path,
        headers={"X-Pawprints-Internal-Service": "event", "X-Pawprints-Internal-Token": "event-secret"},
    )

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json() == {"invalidated": True}
    assert second.json() == {"invalidated": True}
    assert get_user_cache_version(redis_client, USER_A) == before + 2


def test_internal_invalidation_rejects_unauthorized_callers(client):
    response = client.post(
        f"/internal/analytics/users/{USER_A}/invalidate",
        headers={"X-Pawprints-Internal-Service": "media", "X-Pawprints-Internal-Token": "event-secret"},
    )
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "not_authenticated"


def test_internal_invalidation_does_not_change_other_user_version(client, redis_client):
    from app.cache import get_user_cache_version

    target = uuid4()
    other = uuid4()
    before_other = get_user_cache_version(redis_client, other)
    response = client.post(
        f"/internal/analytics/users/{target}/invalidate",
        headers={"X-Pawprints-Internal-Service": "event", "X-Pawprints-Internal-Token": "event-secret"},
    )
    assert response.status_code == 200
    assert get_user_cache_version(redis_client, other) == before_other
