from __future__ import annotations

import hashlib

from sqlalchemy import text

from conftest import register_user, run_two_refresh_requests, set_refresh_expired


def refresh_cookie_value(response) -> str:
    return response.cookies["refresh_token"]


def refresh_hash(response) -> str:
    return hashlib.sha256(refresh_cookie_value(response).encode("utf-8")).hexdigest()


def test_refresh_tokens_are_stored_only_as_sha256_hashes(client, auth_db_session):
    registered = register_user(client)
    plaintext = refresh_cookie_value(registered)

    rows = auth_db_session.execute(text("SELECT token_hash FROM auth.refresh_tokens")).scalars().all()

    assert rows == [hashlib.sha256(plaintext.encode("utf-8")).hexdigest()]
    assert plaintext not in rows


def test_refresh_rotates_and_old_refresh_token_is_rejected(client, auth_db_session):
    login = register_user(client)
    old_hash = refresh_hash(login)

    first = client.post(
        "/api/v1/auth/refresh",
        headers={"Origin": "http://localhost:8080"},
        cookies=login.cookies,
    )
    second = client.post(
        "/api/v1/auth/refresh",
        headers={"Origin": "http://localhost:8080"},
        cookies=login.cookies,
    )

    assert first.status_code == 200
    assert second.status_code == 401
    replacement_id = auth_db_session.execute(
        text("SELECT replaced_by_token_id FROM auth.refresh_tokens WHERE token_hash = :token_hash"),
        {"token_hash": old_hash},
    ).scalar_one()
    assert replacement_id is not None


def test_refresh_rejects_expired_session(client, auth_db_session):
    registered = register_user(client)
    set_refresh_expired(auth_db_session, refresh_hash(registered))

    response = client.post(
        "/api/v1/auth/refresh",
        headers={"Origin": "http://localhost:8080"},
        cookies=registered.cookies,
    )

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "invalid_refresh_token"


def test_logout_revokes_refresh_token_and_clears_cookie(client, auth_db_session):
    registered = register_user(client)
    token_hash = refresh_hash(registered)

    response = client.post(
        "/api/v1/auth/logout",
        headers={"Origin": "http://localhost:8080"},
        cookies=registered.cookies,
    )

    assert response.status_code == 204
    assert "refresh_token=\"\"" in response.headers["set-cookie"]
    revoked_at = auth_db_session.execute(
        text("SELECT revoked_at FROM auth.refresh_tokens WHERE token_hash = :token_hash"),
        {"token_hash": token_hash},
    ).scalar_one()
    assert revoked_at is not None


def test_concurrent_refresh_allows_at_most_one_success(client):
    registered = register_user(client)

    statuses = run_two_refresh_requests(client, registered.cookies)

    assert sum(status == 200 for status in statuses) == 1
    assert sum(status == 401 for status in statuses) == 1
