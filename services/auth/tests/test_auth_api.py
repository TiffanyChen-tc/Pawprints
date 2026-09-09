from __future__ import annotations

import jwt

from conftest import login_user, register_user


def test_register_creates_session_sets_cookie_and_returns_access_token(client):
    response = client.post(
        "/api/v1/auth/register",
        json={
            "email": " User@Example.COM ",
            "password": "correct horse battery",
            "display_name": "User",
        },
    )

    body = response.json()
    assert response.status_code == 201
    assert response.headers["Cache-Control"] == "no-store"
    assert "refresh_token=" in response.headers["set-cookie"]
    assert "HttpOnly" in response.headers["set-cookie"]
    assert "Path=/api/v1/auth" in response.headers["set-cookie"]
    assert body["token_type"] == "Bearer"
    assert body["expires_in"] == 900
    assert body["user"]["email"] == "user@example.com"
    assert body["user"]["display_name"] == "User"
    assert jwt.get_unverified_header(body["access_token"])["alg"] == "RS256"


def test_register_normalizes_email_without_provider_specific_rewriting(client):
    response = client.post(
        "/api/v1/auth/register",
        json={
            "email": " First.Last+tag@Gmail.COM ",
            "password": "correct horse battery",
            "display_name": None,
        },
    )

    assert response.status_code == 201
    assert response.json()["user"]["email"] == "first.last+tag@gmail.com"


def test_register_invalid_email_uses_error_envelope(client):
    response = client.post(
        "/api/v1/auth/register",
        json={
            "email": "not-an-email",
            "password": "correct horse battery",
            "display_name": None,
        },
    )

    assert response.status_code == 422
    assert response.headers["Cache-Control"] == "no-store"
    assert response.json()["error"]["code"] == "validation_failed"


def test_login_uses_generic_invalid_credential_errors(client):
    register_user(client)

    response = login_user(client, password="wrong horse battery")

    assert response.status_code == 401
    assert response.headers["Cache-Control"] == "no-store"
    assert response.json()["error"]["code"] == "invalid_credentials"
    assert "password" not in response.json()["error"]["message"].lower()


def test_login_invalid_email_uses_generic_invalid_credentials(client):
    response = login_user(client, email="not-an-email")

    assert response.status_code == 401
    assert response.headers["Cache-Control"] == "no-store"
    assert response.json()["error"]["code"] == "invalid_credentials"


def test_login_returns_session_for_existing_user(client):
    register_user(client, email=" User@Example.COM ")

    response = login_user(client, email="user@example.com")

    assert response.status_code == 200
    assert response.headers["Cache-Control"] == "no-store"
    assert response.json()["token_type"] == "Bearer"
    assert response.json()["expires_in"] == 900


def test_me_returns_current_user_from_access_token(client):
    registered = register_user(client)
    token = registered.json()["access_token"]

    response = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    assert response.json()["email"] == "user@example.com"


def test_me_rejects_missing_access_token(client):
    response = client.get("/api/v1/auth/me")

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "not_authenticated"


def test_refresh_rejects_origin_not_in_allowlist(client):
    registered = register_user(client)

    response = client.post(
        "/api/v1/auth/refresh",
        headers={"Origin": "http://evil.example"},
        cookies=registered.cookies,
    )

    assert response.status_code == 403
    assert response.headers["Cache-Control"] == "no-store"
    assert response.json()["error"]["code"] == "origin_not_allowed"


def test_logout_rejects_origin_not_in_allowlist(client):
    registered = register_user(client)

    response = client.post(
        "/api/v1/auth/logout",
        headers={"Origin": "http://evil.example"},
        cookies=registered.cookies,
    )

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "origin_not_allowed"
