from __future__ import annotations

from conftest import create_event


def test_timeline_orders_by_occurred_at_ascending(client, token_a, category_a):
    create_event(client, token_a, category_a["id"], title="Evening", local_datetime="2026-09-09T18:00:00")
    create_event(client, token_a, category_a["id"], title="Morning", local_datetime="2026-09-09T08:00:00")

    response = client.get("/api/v1/events/timeline?date=2026-09-09", headers={"Authorization": f"Bearer {token_a}"})

    assert response.status_code == 200
    assert [item["title"] for item in response.json()["items"]] == ["Morning", "Evening"]


def test_timeline_is_user_scoped(client, token_a, token_b, category_a):
    create_event(client, token_a, category_a["id"], title="Private", local_datetime="2026-09-09T08:00:00")

    response = client.get("/api/v1/events/timeline?date=2026-09-09", headers={"Authorization": f"Bearer {token_b}"})

    assert response.status_code == 200
    assert response.json()["items"] == []


def test_search_is_user_scoped_at_query_level(client, token_a, token_b, category_a):
    create_event(client, token_a, category_a["id"], title="Private needle", local_datetime="2026-09-09T10:00:00")

    response = client.get("/api/v1/events/search?keyword=needle", headers={"Authorization": f"Bearer {token_b}"})

    assert response.status_code == 200
    assert response.json()["items"] == []


def test_search_filters_keyword_dates_category_mood_and_location(client, token_a, category_a):
    create_event(
        client,
        token_a,
        category_a["id"],
        title="Morning run",
        description="river tempo",
        mood="good",
        location_name="Riverside",
        local_datetime="2026-09-09T08:00:00",
    )
    create_event(
        client,
        token_a,
        category_a["id"],
        title="Dinner",
        description="quiet meal",
        mood="neutral",
        location_name="Kitchen",
        local_datetime="2026-09-10T19:00:00",
    )

    response = client.get(
        f"/api/v1/events/search?keyword=tempo&start_date=2026-09-09&end_date=2026-09-09&category_id={category_a['id']}&mood=good&location=river",
        headers={"Authorization": f"Bearer {token_a}"},
    )

    assert response.status_code == 200
    assert [item["title"] for item in response.json()["items"]] == ["Morning run"]


def test_search_orders_newest_first_and_uses_bounded_pagination(client, token_a, category_a):
    create_event(client, token_a, category_a["id"], title="Older", local_datetime="2026-09-09T08:00:00")
    create_event(client, token_a, category_a["id"], title="Newer", local_datetime="2026-09-10T08:00:00")

    response = client.get("/api/v1/events/search?limit=1", headers={"Authorization": f"Bearer {token_a}"})

    assert response.status_code == 200
    assert response.json()["items"][0]["title"] == "Newer"
    assert len(response.json()["items"]) == 1
