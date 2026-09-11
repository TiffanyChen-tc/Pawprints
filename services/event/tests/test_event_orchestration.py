from __future__ import annotations

from types import SimpleNamespace
from uuid import UUID, uuid4

import httpx
from sqlalchemy import create_engine, select, update
from sqlalchemy.orm import Session

from conftest import USER_A, bearer, create_event, patch_event, rename_category


def event_exists(database_url: str, event_id: str) -> bool:
    engine = create_engine(database_url)
    try:
        with Session(engine) as session:
            from app.models import Event

            return session.scalar(select(Event.id).where(Event.id == UUID(event_id))) is not None
    finally:
        engine.dispose()


def test_delete_closes_read_transaction_then_cleans_media_before_final_delete(
    client, monkeypatch, token_a, event_a, event_database_url
):
    import app.events

    engine = create_engine(event_database_url)
    observed_session = Session(engine)
    cleanup_observed = []

    def override_db():
        yield observed_session

    def cleanup(event_id, propagated_request_id, settings):
        assert not observed_session.in_transaction()
        assert event_exists(event_database_url, str(event_id))
        assert propagated_request_id == "delete-order"
        cleanup_observed.append(event_id)

    invalidations = []

    def invalidate(user_id, propagated_request_id, settings):
        assert user_id == USER_A
        assert propagated_request_id == "delete-order"
        assert not event_exists(event_database_url, event_a["id"])
        invalidations.append((user_id, propagated_request_id))

    client.app.dependency_overrides[app.events.get_db] = override_db
    monkeypatch.setattr(app.events, "cleanup_event_media", cleanup, raising=False)
    monkeypatch.setattr(app.events, "invalidate_user_analytics", invalidate)
    try:
        response = client.delete(
            f"/api/v1/events/{event_a['id']}",
            headers={**bearer(token_a), "If-Match": '"1"', "X-Request-Id": "delete-order"},
        )
    finally:
        client.app.dependency_overrides.clear()
        observed_session.close()
        engine.dispose()

    assert response.status_code == 204
    assert cleanup_observed == [UUID(event_a["id"])]
    assert not event_exists(event_database_url, event_a["id"])
    assert invalidations == [(USER_A, "delete-order")]


def test_media_cleanup_failure_keeps_event(client, monkeypatch, token_a, event_a, event_database_url):
    import app.events

    def fail_cleanup(event_id, propagated_request_id, settings):
        raise httpx.HTTPError("media unavailable")

    invalidations = []
    monkeypatch.setattr(app.events, "cleanup_event_media", fail_cleanup, raising=False)
    monkeypatch.setattr(app.events, "invalidate_user_analytics", lambda *args: invalidations.append(args))

    response = client.delete(
        f"/api/v1/events/{event_a['id']}", headers={**bearer(token_a), "If-Match": '"1"'}
    )

    assert response.status_code == 502
    assert event_exists(event_database_url, event_a["id"])
    assert invalidations == []


def test_delete_precondition_failures_never_call_media_cleanup(
    client, monkeypatch, token_a, token_b, event_a
):
    import app.events

    cleanup_calls = []
    monkeypatch.setattr(app.events, "cleanup_event_media", lambda *args: cleanup_calls.append(args), raising=False)

    missing_if_match = client.delete(f"/api/v1/events/{event_a['id']}", headers=bearer(token_a))
    stale = client.delete(
        f"/api/v1/events/{event_a['id']}", headers={**bearer(token_a), "If-Match": '"2"'}
    )
    foreign = client.delete(
        f"/api/v1/events/{event_a['id']}", headers={**bearer(token_b), "If-Match": '"1"'}
    )
    missing = client.delete(
        f"/api/v1/events/{uuid4()}", headers={**bearer(token_a), "If-Match": '"1"'}
    )

    assert [missing_if_match.status_code, stale.status_code, foreign.status_code, missing.status_code] == [428, 412, 404, 404]
    assert cleanup_calls == []


def test_final_delete_is_version_conditional_after_media_cleanup(
    client, monkeypatch, token_a, event_a, event_database_url
):
    import app.events
    from app.models import Event

    def concurrent_update(event_id, propagated_request_id, settings):
        engine = create_engine(event_database_url)
        try:
            with Session(engine) as session:
                session.execute(
                    update(Event).where(Event.id == event_id).values(title="Concurrent", version=Event.version + 1)
                )
                session.commit()
        finally:
            engine.dispose()

    invalidations = []
    monkeypatch.setattr(app.events, "cleanup_event_media", concurrent_update, raising=False)
    monkeypatch.setattr(app.events, "invalidate_user_analytics", lambda *args: invalidations.append(args))

    response = client.delete(
        f"/api/v1/events/{event_a['id']}", headers={**bearer(token_a), "If-Match": '"1"'}
    )

    assert response.status_code == 412
    assert event_exists(event_database_url, event_a["id"])
    assert invalidations == []


def test_successful_create_update_and_category_rename_invalidate_only_after_commit(
    client, monkeypatch, token_a, category_a, event_database_url
):
    import app.categories
    import app.events
    from app.models import Category, Event

    engine = create_engine(event_database_url)
    request_session = Session(engine)
    observed = []
    transaction_states = []

    def override_db():
        yield request_session

    def observe_event_commit(user_id, propagated_request_id, settings):
        transaction_states.append((propagated_request_id, request_session.in_transaction()))
        observer_engine = create_engine(event_database_url)
        try:
            with Session(observer_engine) as session:
                titles = set(session.scalars(select(Event.title).where(Event.user_id == user_id)).all())
                observed.append((propagated_request_id, titles))
        finally:
            observer_engine.dispose()

    def observe_category_commit(user_id, propagated_request_id, settings):
        transaction_states.append((propagated_request_id, request_session.in_transaction()))
        observer_engine = create_engine(event_database_url)
        try:
            with Session(observer_engine) as session:
                names = set(session.scalars(select(Category.name).where(Category.user_id == user_id)).all())
                observed.append((propagated_request_id, names))
        finally:
            observer_engine.dispose()

    client.app.dependency_overrides[app.events.get_db] = override_db
    client.app.dependency_overrides[app.categories.get_db] = override_db
    monkeypatch.setattr(app.events, "invalidate_user_analytics", observe_event_commit)
    monkeypatch.setattr(app.categories, "invalidate_user_analytics", observe_category_commit)

    try:
        created = client.post(
            "/api/v1/events",
            headers={**bearer(token_a), "X-Request-Id": "create-id"},
            json={
                "title": "Created and committed",
                "category_id": category_a["id"],
                "local_datetime": "2026-09-09T08:00:00",
                "timezone": "Asia/Taipei",
            },
        )
        patched = client.patch(
            f"/api/v1/events/{created.json()['id']}",
            headers={**bearer(token_a), "If-Match": '"1"', "X-Request-Id": "patch-id"},
            json={"title": "Updated and committed"},
        )
        renamed = client.patch(
            f"/api/v1/categories/{category_a['id']}",
            headers={**bearer(token_a), "If-Match": '"1"', "X-Request-Id": "rename-id"},
            json={"name": "Renamed and committed"},
        )
    finally:
        client.app.dependency_overrides.clear()
        request_session.close()
        engine.dispose()

    assert [created.status_code, patched.status_code, renamed.status_code] == [201, 200, 200]
    assert observed == [
        ("create-id", {"Created and committed"}),
        ("patch-id", {"Updated and committed"}),
        ("rename-id", {"Renamed and committed"}),
    ]
    assert transaction_states == [("create-id", False), ("patch-id", False), ("rename-id", False)]


def test_failed_create_update_rename_and_delete_do_not_invalidate(
    client, monkeypatch, token_a, category_a, event_a
):
    import app.categories
    import app.events

    invalidations = []
    monkeypatch.setattr(app.events, "invalidate_user_analytics", lambda *args: invalidations.append(args))
    monkeypatch.setattr(app.categories, "invalidate_user_analytics", lambda *args: invalidations.append(args))
    monkeypatch.setattr(app.events, "cleanup_event_media", lambda *args: None, raising=False)

    failed_create = create_event(client, token_a, str(uuid4()))
    failed_update = patch_event(client, token_a, event_a["id"], '"2"', {"title": "No"})
    failed_rename = rename_category(client, token_a, category_a["id"], '"2"', "No")
    failed_delete = client.delete(
        f"/api/v1/events/{event_a['id']}", headers={**bearer(token_a), "If-Match": '"2"'}
    )

    assert [failed_create.status_code, failed_update.status_code, failed_rename.status_code, failed_delete.status_code] == [404, 412, 412, 412]
    assert invalidations == []


def test_internal_clients_use_event_credentials_and_propagate_request_id(monkeypatch):
    import app.clients

    requests = []

    def handle(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json={"ok": True})

    internal_client = httpx.Client(transport=httpx.MockTransport(handle), timeout=2.0)
    monkeypatch.setattr(app.clients, "_client", internal_client)
    settings = SimpleNamespace(
        media_service_url="http://media.local",
        analytics_service_url="http://analytics.local",
        event_internal_token="event-secret",
    )
    event_id = uuid4()

    app.clients.cleanup_event_media(event_id, "request-123", settings)
    app.clients.invalidate_user_analytics(USER_A, "request-123", settings)

    assert [str(request.url) for request in requests] == [
        f"http://media.local/internal/media/events/{event_id}/cleanup",
        f"http://analytics.local/internal/analytics/users/{USER_A}/invalidate",
    ]
    for request in requests:
        assert request.headers["X-Pawprints-Internal-Service"] == "event"
        assert request.headers["X-Pawprints-Internal-Token"] == "event-secret"
        assert request.headers["X-Request-Id"] == "request-123"


def test_analytics_invalidation_http_failure_is_best_effort(monkeypatch):
    import app.clients

    def handle(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, request=request)

    monkeypatch.setattr(app.clients, "_client", httpx.Client(transport=httpx.MockTransport(handle), timeout=2.0))
    settings = SimpleNamespace(analytics_service_url="http://analytics.local", event_internal_token="event-secret")

    app.clients.invalidate_user_analytics(USER_A, "request-503", settings)


def test_analytics_failure_does_not_roll_back_successful_mutations(
    client, monkeypatch, token_a, category_a, event_database_url
):
    import app.clients

    def handle(request: httpx.Request) -> httpx.Response:
        status_code = 200 if "/internal/media/" in request.url.path else 503
        return httpx.Response(status_code, request=request, json={"ok": status_code == 200})

    monkeypatch.setattr(app.clients, "_client", httpx.Client(transport=httpx.MockTransport(handle), timeout=2.0))

    created = create_event(client, token_a, category_a["id"], title="Survives analytics failure")
    patched = patch_event(client, token_a, created.json()["id"], '"1"', {"title": "Still committed"})
    renamed = rename_category(client, token_a, category_a["id"], '"1"', "Still renamed")
    deleted = client.delete(
        f"/api/v1/events/{created.json()['id']}", headers={**bearer(token_a), "If-Match": '"2"'}
    )

    assert [created.status_code, patched.status_code, renamed.status_code, deleted.status_code] == [201, 200, 200, 204]
    assert not event_exists(event_database_url, created.json()["id"])
