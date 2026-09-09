from __future__ import annotations

from sqlalchemy import text


def test_auth_migration_uses_auth_schema_version_table(auth_db_session):
    row = auth_db_session.execute(
        text(
            "select to_regclass('auth.users')::text, "
            "to_regclass('auth.refresh_tokens')::text, "
            "to_regclass('auth.alembic_version')::text, "
            "to_regclass('public.alembic_version')::text"
        )
    ).one()

    assert row == ("auth.users", "auth.refresh_tokens", "auth.alembic_version", None)
