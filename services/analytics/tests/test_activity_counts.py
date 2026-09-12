from __future__ import annotations

from datetime import date, datetime, timezone
from uuid import uuid4

from conftest import USER_A, USER_B, bearer, insert_fact


def test_activity_counts_requires_bearer_authentication(client):
    response = client.get(
        "/api/v1/analytics/activity-counts?start_date=2026-09-01&end_date=2026-09-30"
    )
    assert response.status_code == 401
    assert response.headers["WWW-Authenticate"] == "Bearer"
    assert response.json()["error"]["code"] == "not_authenticated"


def test_activity_counts_exclude_other_users(client, token_a, event_engine):
    category_a = uuid4()
    category_b = uuid4()
    insert_fact(event_engine, user_id=USER_A, category_id=category_a, category_name="Running", local_date=date(2026, 9, 2))
    insert_fact(event_engine, user_id=USER_A, category_id=category_a, category_name="Running", local_date=date(2026, 9, 3))
    insert_fact(event_engine, user_id=USER_B, category_id=category_b, category_name="Private", local_date=date(2026, 9, 2))

    response = client.get(
        "/api/v1/analytics/activity-counts?start_date=2026-09-01&end_date=2026-09-30",
        headers=bearer(token_a),
    )

    assert response.status_code == 200
    assert response.json()["items"] == [
        {"category_id": str(category_a), "category_name": "Running", "count": 2}
    ]


def test_spoofed_user_header_does_not_change_analytics_identity(client, token_a, event_engine):
    category_a = uuid4()
    category_b = uuid4()
    insert_fact(event_engine, user_id=USER_A, category_id=category_a, category_name="Running", local_date=date(2026, 9, 2))
    insert_fact(event_engine, user_id=USER_B, category_id=category_b, category_name="Private", local_date=date(2026, 9, 2))

    response = client.get(
        "/api/v1/analytics/activity-counts?start_date=2026-09-01&end_date=2026-09-30",
        headers={**bearer(token_a), "X-User-Id": str(USER_B)},
    )

    assert response.status_code == 200
    assert response.json()["items"] == [
        {"category_id": str(category_a), "category_name": "Running", "count": 1}
    ]


def test_category_and_inclusive_date_range_filters(client, token_a, event_engine):
    running = uuid4()
    reading = uuid4()
    insert_fact(event_engine, user_id=USER_A, category_id=running, category_name="Running", local_date=date(2026, 8, 31))
    insert_fact(event_engine, user_id=USER_A, category_id=running, category_name="Running", local_date=date(2026, 9, 1))
    insert_fact(event_engine, user_id=USER_A, category_id=running, category_name="Running", local_date=date(2026, 9, 30))
    insert_fact(event_engine, user_id=USER_A, category_id=reading, category_name="Reading", local_date=date(2026, 9, 15))
    insert_fact(event_engine, user_id=USER_A, category_id=running, category_name="Running", local_date=date(2026, 10, 1))

    response = client.get(
        "/api/v1/analytics/activity-counts",
        params={"start_date": "2026-09-01", "end_date": "2026-09-30", "category_id": str(running)},
        headers=bearer(token_a),
    )

    assert response.status_code == 200
    assert response.json()["items"] == [
        {"category_id": str(running), "category_name": "Running", "count": 2}
    ]


def test_equal_range_filters_one_local_date_not_utc_date(client, token_a, event_engine):
    running = uuid4()
    insert_fact(
        event_engine,
        user_id=USER_A,
        category_id=running,
        category_name="Running",
        local_date=date(2026, 9, 1),
        occurred_at=datetime(2026, 8, 31, 16, 30, tzinfo=timezone.utc),
    )

    response = client.get(
        "/api/v1/analytics/activity-counts?start_date=2026-09-01&end_date=2026-09-01",
        headers=bearer(token_a),
    )

    assert response.status_code == 200
    assert response.json()["items"][0]["count"] == 1


def test_weekly_grouping_uses_iso_monday_buckets(client, token_a, event_engine):
    running = uuid4()
    for local_day in (date(2026, 9, 1), date(2026, 9, 6), date(2026, 9, 7)):
        insert_fact(event_engine, user_id=USER_A, category_id=running, category_name="Running", local_date=local_day)

    response = client.get(
        "/api/v1/analytics/activity-counts?start_date=2026-09-01&end_date=2026-09-30&grouping=week",
        headers=bearer(token_a),
    )

    assert response.status_code == 200
    assert response.json()["buckets"] == [
        {
            "bucket_start_date": "2026-08-31",
            "items": [{"category_id": str(running), "category_name": "Running", "count": 2}],
        },
        {
            "bucket_start_date": "2026-09-07",
            "items": [{"category_id": str(running), "category_name": "Running", "count": 1}],
        },
    ]


def test_monthly_grouping_uses_calendar_month_buckets(client, token_a, event_engine):
    reading = uuid4()
    for local_day in (date(2026, 9, 30), date(2026, 10, 1)):
        insert_fact(event_engine, user_id=USER_A, category_id=reading, category_name="Reading", local_date=local_day)

    response = client.get(
        "/api/v1/analytics/activity-counts?start_date=2026-09-01&end_date=2026-10-31&grouping=month",
        headers=bearer(token_a),
    )

    assert response.status_code == 200
    assert [bucket["bucket_start_date"] for bucket in response.json()["buckets"]] == ["2026-09-01", "2026-10-01"]


def test_empty_range_returns_valid_empty_response(client, token_a):
    response = client.get(
        "/api/v1/analytics/activity-counts?start_date=2026-09-01&end_date=2026-09-30",
        headers=bearer(token_a),
    )
    assert response.status_code == 200
    assert response.json()["items"] == []


def test_reversed_date_range_is_rejected(client, token_a):
    response = client.get(
        "/api/v1/analytics/activity-counts?start_date=2026-10-01&end_date=2026-09-30",
        headers=bearer(token_a),
    )
    assert response.status_code == 422
