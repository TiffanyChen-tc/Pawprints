from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Header, Request
from redis.exceptions import RedisError

from pawprints_common.internal_auth import InternalAuthError, verify_internal_request

from app.cache import get_redis, invalidate_user
from app.config import Settings, get_settings
from app.routes import api_error


router = APIRouter(prefix="/internal/analytics/users")


@router.post("/{user_id}/invalidate")
def invalidate_user_cache(
    user_id: UUID,
    request: Request,
    x_pawprints_internal_service: str | None = Header(default=None),
    x_pawprints_internal_token: str | None = Header(default=None),
    settings: Settings = Depends(get_settings),
):
    try:
        verify_internal_request(
            x_pawprints_internal_service or "",
            x_pawprints_internal_token or "",
            {"event"},
            {"event": settings.event_internal_token},
        )
    except InternalAuthError:
        return api_error(request, "not_authenticated", "Authentication is required.", 401)

    try:
        invalidate_user(get_redis(), user_id)
    except RedisError:
        return api_error(request, "cache_unavailable", "Analytics cache is unavailable.", 503)
    return {"invalidated": True}
