from __future__ import annotations

from uuid import UUID

from fastapi import Request

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


def verify_event_internal(service: str | None, token: str | None, settings: Settings) -> bool:
    try:
        verify_internal_request(
            service or "",
            token or "",
            {"event"},
            {"event": settings.event_internal_token},
        )
        return True
    except InternalAuthError:
        return False
