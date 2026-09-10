from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Header, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.db import get_db
from app.http import api_error, authenticated_user_id, not_found, verify_media_internal
from app.models import Event


router = APIRouter(prefix="/internal/events")


@router.get("/{event_id}/ownership")
def ownership(
    event_id: UUID,
    request: Request,
    authorization: str | None = Header(default=None),
    x_pawprints_internal_service: str | None = Header(default=None),
    x_pawprints_internal_token: str | None = Header(default=None),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    if not verify_media_internal(x_pawprints_internal_service, x_pawprints_internal_token, settings):
        return api_error(request, "not_authenticated", "Authentication is required.", 401)
    user_id = authenticated_user_id(request, authorization, settings)
    if user_id is None:
        return api_error(request, "not_authenticated", "Authentication is required.", 401)
    owned = db.scalar(select(Event.id).where(Event.id == event_id, Event.user_id == user_id))
    if owned is None:
        return not_found(request)
    return {"event_id": str(event_id), "user_id": str(user_id)}
