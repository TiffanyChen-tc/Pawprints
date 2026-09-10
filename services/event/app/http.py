from __future__ import annotations

from uuid import UUID

from fastapi import Header, Request

from pawprints_common.errors import error_response
from pawprints_common.internal_auth import InternalAuthError, verify_internal_request
from pawprints_common.jwt import JWTValidationError, verify_access_token

from app.config import Settings


def request_id(request: Request) -> str:
    return request.headers.get("X-Request-Id", "")


def api_error(request: Request, code: str, message: str, status_code: int):
    return error_response(code, message, status_code, request_id(request))


def not_found(request: Request):
    return api_error(request, "resource_not_found", "Resource was not found.", 404)


def etag(version: int) -> str:
    return f'"{version}"'


def parse_if_match(value: str | None) -> int | None:
    if value is None:
        return None
    if len(value) < 3 or not value.startswith('"') or not value.endswith('"'):
        return -1
    try:
        return int(value[1:-1])
    except ValueError:
        return -1


def load_public_key(settings: Settings) -> str:
    return open(settings.jwt_public_key_path, encoding="utf-8").read()


def authenticated_user_id(request: Request, authorization: str | None, settings: Settings) -> UUID | None:
    if not authorization or not authorization.startswith("Bearer "):
        return None
    try:
        user = verify_access_token(
            authorization.removeprefix("Bearer "),
            load_public_key(settings),
            settings.jwt_issuer,
            settings.jwt_audience,
        )
        return user.user_id
    except JWTValidationError:
        return None


def verify_media_internal(
    x_pawprints_internal_service: str | None = Header(default=None),
    x_pawprints_internal_token: str | None = Header(default=None),
    settings: Settings | None = None,
) -> bool:
    if settings is None:
        return False
    try:
        verify_internal_request(
            x_pawprints_internal_service or "",
            x_pawprints_internal_token or "",
            {"media"},
            {"media": settings.media_internal_token},
        )
        return True
    except InternalAuthError:
        return False
