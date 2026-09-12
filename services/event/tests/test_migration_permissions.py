from __future__ import annotations

import os

from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url


def test_event_migration_places_objects_and_grants_only_analytics_view(event_db_session):
    row = event_db_session.execute(
        text(
            "select to_regclass('events.categories')::text, "
            "to_regclass('events.events')::text, "
            "to_regclass('events.alembic_version')::text, "
            "to_regclass('public.alembic_version')::text, "
            "to_regclass('events.analytics_event_facts')::text"
        )
    ).one()
    assert row == ("events.categories", "events.events", "events.alembic_version", None, "events.analytics_event_facts")


def test_analytics_role_can_select_view_but_not_event_base_tables():
    database_url = os.environ.get(
        "ANALYTICS_DATABASE_URL",
        "postgresql+psycopg://pawprints_analytics_ro:test_analytics@127.0.0.1:55432/pawprints_test",
    )
    engine = create_engine(database_url)
    with engine.connect() as connection:
        assert connection.execute(text("select count(*) from events.analytics_event_facts")).scalar_one() >= 0
        try:
            connection.execute(text("select count(*) from events.events")).scalar_one()
        except Exception as exc:
            assert "permission denied" in str(exc).lower()
        else:
            raise AssertionError("analytics role unexpectedly selected events.events")
    engine.dispose()


def _url_for_test_role(base_url: str, role: str, password: str) -> str:
    url = make_url(base_url)
    return url.set(username=role, password=password).render_as_string(hide_password=False)


def _assert_select_denied(database_url: str, statement: str) -> None:
    engine = create_engine(database_url)
    try:
        with engine.connect() as connection:
            try:
                connection.execute(text(statement)).scalar_one()
            except Exception as exc:
                assert "permission denied" in str(exc).lower()
            else:
                raise AssertionError(f"role unexpectedly executed: {statement}")
    finally:
        engine.dispose()


def _assert_peer_tables_exist(admin_url: str) -> None:
    engine = create_engine(admin_url)
    try:
        with engine.connect() as connection:
            row = connection.execute(
                text(
                    "select to_regclass('auth.users')::text, "
                    "to_regclass('events.events')::text, "
                    "to_regclass('events.categories')::text, "
                    "to_regclass('media.event_media')::text, "
                    "to_regclass('events.analytics_event_facts')::text"
                )
            ).one()
            assert row == (
                "auth.users",
                "events.events",
                "events.categories",
                "media.event_media",
                "events.analytics_event_facts",
            )
    finally:
        engine.dispose()


def test_service_database_roles_cannot_read_peer_owned_tables(event_database_url: str):
    admin_url = _url_for_test_role(event_database_url, "postgres", "postgres")
    auth_url = _url_for_test_role(event_database_url, "pawprints_auth_rw", "test_auth")
    event_url = _url_for_test_role(event_database_url, "pawprints_event_rw", "test_event")
    media_url = _url_for_test_role(event_database_url, "pawprints_media_rw", "test_media")
    analytics_url = _url_for_test_role(event_database_url, "pawprints_analytics_ro", "test_analytics")

    _assert_peer_tables_exist(admin_url)
    _assert_select_denied(auth_url, "select count(*) from events.events")
    _assert_select_denied(auth_url, "select count(*) from media.event_media")
    _assert_select_denied(event_url, "select count(*) from auth.users")
    _assert_select_denied(event_url, "select count(*) from media.event_media")
    _assert_select_denied(media_url, "select count(*) from auth.users")
    _assert_select_denied(media_url, "select count(*) from events.events")
    _assert_select_denied(analytics_url, "select count(*) from auth.users")
    _assert_select_denied(analytics_url, "select count(*) from media.event_media")
