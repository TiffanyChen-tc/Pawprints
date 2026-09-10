from __future__ import annotations

from datetime import date
from uuid import UUID, uuid4

from conftest import USER_A, USER_B, bearer, insert_fact


def test_cache_key_is_deterministic_user_scoped_versioned_and_filter_complete():
    from app.cache import cache_key
    from app.routes import ActivityQuery

    query = ActivityQuery(
        start_date=date(2026, 9, 1),
        end_date=date(2026, 9, 30),
        category_id=UUID("cccccccc-cccc-4ccc-8ccc-cccccccccccc"),
        grouping="week",
    )
    key_a = cache_key(USER_A, 4, query)
    key_a_again = cache_key(USER_A, 4, query)
    key_b = cache_key(USER_B, 4, query)
    changed_filter = cache_key(USER_A, 4, query.model_copy(update={"grouping": "month"}))

    assert key_a == key_a_again
    assert key_a != key_b
    assert key_a != changed_filter
    assert ":user:aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa:" in key_a
    assert ":ver:4:" in key_a


def test_cache_miss_queries_postgres_then_hit_returns_equivalent_result(
    client, token_a, event_engine, redis_client
):
    category_id = uuid4()
    insert_fact(event_engine, user_id=USER_A, category_id=category_id, category_name="Running", local_date=date(2026, 9, 1))
    path = "/api/v1/analytics/activity-counts?start_date=2026-09-01&end_date=2026-09-30"

    first = client.get(path, headers=bearer(token_a))
    assert first.status_code == 200
    assert list(redis_client.scan_iter(f"analytics:v1:user:{USER_A}:*"))

    insert_fact(event_engine, user_id=USER_A, category_id=category_id, category_name="Running", local_date=date(2026, 9, 2))
    second = client.get(path, headers=bearer(token_a))

    assert second.status_code == 200
    assert second.json() == first.json()
    assert second.json()["items"][0]["count"] == 1


def test_one_users_cached_result_cannot_be_reused_by_another_user(
    client, token_a, token_b, event_engine, redis_client
):
    category_a = uuid4()
    category_b = uuid4()
    insert_fact(event_engine, user_id=USER_A, category_id=category_a, category_name="Running", local_date=date(2026, 9, 1))
    insert_fact(event_engine, user_id=USER_B, category_id=category_b, category_name="Reading", local_date=date(2026, 9, 1))
    path = "/api/v1/analytics/activity-counts?start_date=2026-09-01&end_date=2026-09-30"

    response_a = client.get(path, headers=bearer(token_a))
    response_b = client.get(path, headers=bearer(token_b))

    assert response_a.json()["items"][0]["category_id"] == str(category_a)
    assert response_b.json()["items"][0]["category_id"] == str(category_b)
    keys = set(redis_client.scan_iter("analytics:v1:user:*"))
    assert any(str(USER_A) in key for key in keys)
    assert any(str(USER_B) in key for key in keys)


def test_invalidation_increments_only_target_user_version(redis_client):
    from app.cache import get_user_cache_version, invalidate_user

    before_a = get_user_cache_version(redis_client, USER_A)
    before_b = get_user_cache_version(redis_client, USER_B)
    invalidate_user(redis_client, USER_A)

    assert get_user_cache_version(redis_client, USER_A) == before_a + 1
    assert get_user_cache_version(redis_client, USER_B) == before_b
