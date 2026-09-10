from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Header, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.db import get_db
from app.http import api_error, verify_event_internal
from app.models import EventMedia
from app.storage import LocalFileStorage


router = APIRouter(prefix="/internal/media/events")


@router.post("/{event_id}/cleanup")
def cleanup_event_media(
    event_id: UUID,
    request: Request,
    x_pawprints_internal_service: str | None = Header(default=None),
    x_pawprints_internal_token: str | None = Header(default=None),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    if not verify_event_internal(x_pawprints_internal_service, x_pawprints_internal_token, settings):
        return api_error(request, "not_authenticated", "Authentication is required.", 401)
    rows = db.scalars(select(EventMedia).where(EventMedia.event_id == event_id)).all()
    file_storage = LocalFileStorage(settings.media_storage_root)
    for row in rows:
        file_storage.delete(row.storage_key)
    for row in rows:
        db.delete(row)
    db.commit()
    return {"deleted": len(rows)}
