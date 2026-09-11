from __future__ import annotations

import os

from sqlalchemy import create_engine, text


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
