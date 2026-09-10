from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Request, Response, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy import Select, desc, func, select, text
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.db import get_db
from app.event_client import EventClient
from app.http import api_error, authenticated_user_id, not_found, request_id
from app.image_processing import InvalidImageError, NormalizedImage, normalize_image
from app.models import EventMedia
from app.storage import LocalFileStorage


router = APIRouter(prefix="/api/v1/media")


def media_json(media: EventMedia) -> dict[str, object]:
    return {
        "id": str(media.id),
        "event_id": str(media.event_id),
        "mime_type": media.mime_type,
        "file_size": media.file_size,
        "display_order": media.display_order,
        "created_at": media.created_at.isoformat(),
    }


def storage(settings: Settings) -> LocalFileStorage:
    return LocalFileStorage(settings.media_storage_root)


def require_user_and_event(
    request: Request,
    event_id: UUID,
    authorization: str | None,
    settings: Settings,
) -> bool:
    if authenticated_user_id(request, authorization, settings) is None or authorization is None:
        return False
    return EventClient(settings).verify_ownership(event_id, authorization, request_id(request))


def cleanup_written_files(file_storage: LocalFileStorage, keys: list[str]) -> None:
    for key in keys:
        try:
            file_storage.delete(key)
        except OSError:
            pass


@router.post("/events/{event_id}", status_code=201)
def upload_event_media(
    event_id: UUID,
    request: Request,
    files: list[UploadFile],
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    if not require_user_and_event(request, event_id, authorization, settings):
        return not_found(request)
    normalized: list[NormalizedImage] = []
    try:
        for upload in files:
            normalized.append(
                normalize_image(
                    upload.file.read(),
                    max_bytes=settings.media_max_file_bytes,
                    max_pixels=settings.media_max_pixels,
                )
            )
    except InvalidImageError:
        return api_error(request, "invalid_media", "Uploaded media is invalid.", 422)
    if not normalized:
        return api_error(request, "validation_failed", "At least one file is required.", 422)

    file_storage = storage(settings)
    written_keys: list[str] = []
    try:
        with db.begin():
            db.execute(text("SELECT pg_advisory_xact_lock(hashtextextended(:event_id, 0))"), {"event_id": str(event_id)})
            existing_count = db.scalar(select(func.count(EventMedia.id)).where(EventMedia.event_id == event_id)) or 0
            if existing_count + len(normalized) > settings.media_max_images_per_event:
                return api_error(request, "media_limit_exceeded", "An event can have at most five images.", 409)
            last_order = (
                db.scalar(select(EventMedia.display_order).where(EventMedia.event_id == event_id).order_by(desc(EventMedia.display_order)).limit(1))
                or 0
            )
            rows: list[EventMedia] = []
            for index, image in enumerate(normalized, start=1):
                key = file_storage.generate_key()
                file_storage.write(key, image.bytes)
                written_keys.append(key)
                row = EventMedia(
                    event_id=event_id,
                    storage_key=key,
                    mime_type=image.mime_type,
                    file_size=image.file_size,
                    display_order=last_order + index,
                    created_at=datetime.now(timezone.utc),
                )
                db.add(row)
                rows.append(row)
            db.flush()
        return [media_json(row) for row in rows]
    except OSError:
        db.rollback()
        cleanup_written_files(file_storage, written_keys)
        return api_error(request, "media_storage_failed", "Media could not be stored.", 500)
    except Exception:
        db.rollback()
        cleanup_written_files(file_storage, written_keys)
        raise


@router.get("/events/{event_id}")
def list_event_media(
    event_id: UUID,
    request: Request,
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    if not require_user_and_event(request, event_id, authorization, settings):
        return not_found(request)
    rows = db.scalars(select(EventMedia).where(EventMedia.event_id == event_id).order_by(EventMedia.display_order)).all()
    return [media_json(row) for row in rows]


def media_by_id_query(media_id: UUID) -> Select[tuple[EventMedia]]:
    return select(EventMedia).where(EventMedia.id == media_id)


@router.get("/{media_id}")
def retrieve_media(
    media_id: UUID,
    request: Request,
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    row = db.scalar(media_by_id_query(media_id))
    if row is None or not require_user_and_event(request, row.event_id, authorization, settings):
        return not_found(request)
    return StreamingResponse(storage(settings).read(row.storage_key), media_type=row.mime_type)


@router.delete("/{media_id}", status_code=204)
def delete_media(
    media_id: UUID,
    request: Request,
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    row = db.scalar(media_by_id_query(media_id))
    if row is None or not require_user_and_event(request, row.event_id, authorization, settings):
        return not_found(request)
    key = row.storage_key
    db.delete(row)
    try:
        storage(settings).delete(key)
    except OSError:
        db.rollback()
        return api_error(request, "media_storage_failed", "Media could not be deleted.", 500)
    db.commit()
    return Response(status_code=204)
