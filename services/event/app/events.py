from __future__ import annotations

from datetime import date as LocalDate, datetime, timezone
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo

import httpx
from fastapi import APIRouter, Depends, Header, Request, Response, status
from sqlalchemy import delete, select, update
from sqlalchemy.orm import Session, joinedload

from app.clients import cleanup_event_media, invalidate_user_analytics
from app.config import Settings, get_settings
from app.db import get_db
from app.http import api_error, authenticated_user_id, etag, not_found, parse_if_match, request_id
from app.models import Category, Event
from app.schemas import EventCreate, EventOut, EventPatch
from app.time_semantics import EventValidationError, derive_event_time


router = APIRouter(prefix="/api/v1/events")


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def event_out(event: Event) -> dict:
    data = EventOut(
        id=event.id,
        category_id=event.category_id,
        title=event.title,
        description=event.description,
        mood=event.mood,
        location_name=event.location_name,
        latitude=event.latitude,
        longitude=event.longitude,
        occurred_at=event.occurred_at,
        timezone=event.timezone,
        local_date=event.local_date,
        version=event.version,
        category_name=event.category.name,
    ).model_dump(mode="json")
    if data["occurred_at"].endswith("+00:00"):
        data["occurred_at"] = data["occurred_at"][:-6] + "Z"
    return data


def get_owned_event(db: Session, event_id: UUID, user_id: UUID) -> Event | None:
    return db.scalar(select(Event).options(joinedload(Event.category)).where(Event.id == event_id, Event.user_id == user_id))


@router.post("", status_code=status.HTTP_201_CREATED)
def create_event(payload: EventCreate, request: Request, response: Response, authorization: str | None = Header(default=None), db: Session = Depends(get_db), settings: Settings = Depends(get_settings)):
    user_id = authenticated_user_id(request, authorization, settings)
    if user_id is None:
        return api_error(request, "not_authenticated", "Authentication is required.", 401)
    category = db.scalar(select(Category).where(Category.id == payload.category_id, Category.user_id == user_id))
    if category is None:
        return not_found(request)
    try:
        event_time = derive_event_time(payload.local_datetime, payload.timezone)
    except EventValidationError:
        return api_error(request, "validation_failed", "Some fields are invalid.", 422)
    event = Event(
        id=uuid4(),
        user_id=user_id,
        category_id=category.id,
        title=payload.title.strip(),
        description=payload.description,
        mood=payload.mood,
        location_name=payload.location_name,
        latitude=payload.latitude,
        longitude=payload.longitude,
        occurred_at=event_time.occurred_at,
        timezone=event_time.timezone,
        local_date=event_time.local_date,
        version=1,
        created_at=now_utc(),
        updated_at=now_utc(),
    )
    db.add(event)
    db.commit()
    db.refresh(event)
    event.category = category
    response.headers["ETag"] = etag(event.version)
    body = event_out(event)
    db.rollback()
    invalidate_user_analytics(user_id, request_id(request), settings)
    return body


@router.get("/timeline")
def timeline(date: LocalDate, request: Request, authorization: str | None = Header(default=None), db: Session = Depends(get_db), settings: Settings = Depends(get_settings)):
    user_id = authenticated_user_id(request, authorization, settings)
    if user_id is None:
        return api_error(request, "not_authenticated", "Authentication is required.", 401)
    events = db.scalars(
        select(Event)
        .options(joinedload(Event.category))
        .where(Event.user_id == user_id, Event.local_date == date)
        .order_by(Event.occurred_at.asc())
    ).all()
    return {"items": [event_out(event) for event in events]}


@router.get("/search")
def search(
    request: Request,
    authorization: str | None = Header(default=None),
    keyword: str | None = None,
    date: LocalDate | None = None,
    start_date: LocalDate | None = None,
    end_date: LocalDate | None = None,
    category_id: UUID | None = None,
    mood: str | None = None,
    location: str | None = None,
    limit: int = 50,
    offset: int = 0,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    user_id = authenticated_user_id(request, authorization, settings)
    if user_id is None:
        return api_error(request, "not_authenticated", "Authentication is required.", 401)
    limit = max(1, min(limit, 100))
    query = select(Event).options(joinedload(Event.category)).where(Event.user_id == user_id)
    if keyword:
        like = f"%{keyword}%"
        query = query.where(Event.title.ilike(like) | Event.description.ilike(like) | Event.location_name.ilike(like))
    if date:
        query = query.where(Event.local_date == date)
    if start_date:
        query = query.where(Event.local_date >= start_date)
    if end_date:
        query = query.where(Event.local_date <= end_date)
    if category_id:
        query = query.where(Event.category_id == category_id)
    if mood:
        query = query.where(Event.mood == mood)
    if location:
        query = query.where(Event.location_name.ilike(f"%{location}%"))
    events = db.scalars(query.order_by(Event.occurred_at.desc()).limit(limit).offset(max(0, offset))).all()
    return {"items": [event_out(event) for event in events], "limit": limit, "offset": max(0, offset)}


@router.get("/{event_id}")
def get_event(event_id: UUID, request: Request, response: Response, authorization: str | None = Header(default=None), db: Session = Depends(get_db), settings: Settings = Depends(get_settings)):
    user_id = authenticated_user_id(request, authorization, settings)
    if user_id is None:
        return api_error(request, "not_authenticated", "Authentication is required.", 401)
    event = get_owned_event(db, event_id, user_id)
    if event is None:
        return not_found(request)
    response.headers["ETag"] = etag(event.version)
    return event_out(event)


@router.patch("/{event_id}")
def patch_event(event_id: UUID, payload: EventPatch, request: Request, response: Response, authorization: str | None = Header(default=None), if_match: str | None = Header(default=None), db: Session = Depends(get_db), settings: Settings = Depends(get_settings)):
    user_id = authenticated_user_id(request, authorization, settings)
    if user_id is None:
        return api_error(request, "not_authenticated", "Authentication is required.", 401)
    expected_version = parse_if_match(if_match)
    if expected_version is None:
        return api_error(request, "precondition_required", "If-Match is required.", 428)
    current = get_owned_event(db, event_id, user_id)
    if current is None:
        return not_found(request)
    values = {"updated_at": now_utc(), "version": Event.version + 1}
    if payload.category_id is not None:
        category = db.scalar(select(Category).where(Category.id == payload.category_id, Category.user_id == user_id))
        if category is None:
            return not_found(request)
        values["category_id"] = payload.category_id
    for field in ("title", "description", "mood", "location_name", "latitude", "longitude"):
        value = getattr(payload, field)
        if value is not None:
            values[field] = value.strip() if field == "title" else value
    if payload.local_datetime is not None or payload.timezone is not None:
        local_datetime = payload.local_datetime
        if local_datetime is None:
            local_datetime = current.occurred_at.astimezone(ZoneInfo(current.timezone)).replace(tzinfo=None).isoformat()
        try:
            event_time = derive_event_time(local_datetime, payload.timezone or current.timezone)
        except EventValidationError:
            return api_error(request, "validation_failed", "Some fields are invalid.", 422)
        values["occurred_at"] = event_time.occurred_at
        values["timezone"] = event_time.timezone
        values["local_date"] = event_time.local_date

    result = db.execute(
        update(Event)
        .where(Event.id == event_id, Event.user_id == user_id, Event.version == expected_version)
        .values(**values)
        .returning(Event.id)
    ).first()
    if result is None:
        db.rollback()
        return api_error(request, "stale_version", "This Pawprint changed since you opened it.", 412)
    db.commit()
    updated = get_owned_event(db, event_id, user_id)
    response.headers["ETag"] = etag(updated.version)
    body = event_out(updated)
    db.rollback()
    invalidate_user_analytics(user_id, request_id(request), settings)
    return body


@router.delete("/{event_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_event(event_id: UUID, request: Request, response: Response, authorization: str | None = Header(default=None), if_match: str | None = Header(default=None), db: Session = Depends(get_db), settings: Settings = Depends(get_settings)):
    user_id = authenticated_user_id(request, authorization, settings)
    if user_id is None:
        return api_error(request, "not_authenticated", "Authentication is required.", 401)
    expected_version = parse_if_match(if_match)
    if expected_version is None:
        return api_error(request, "precondition_required", "If-Match is required.", 428)
    current_version = db.scalar(select(Event.version).where(Event.id == event_id, Event.user_id == user_id))
    if current_version is None:
        return not_found(request)
    if current_version != expected_version:
        db.rollback()
        return api_error(request, "stale_version", "This Pawprint changed since you opened it.", 412)

    db.rollback()
    propagated_request_id = request_id(request)
    try:
        cleanup_event_media(event_id, propagated_request_id, settings)
    except httpx.HTTPError:
        return api_error(request, "media_cleanup_failed", "Media cleanup failed.", 502)

    result = db.execute(delete(Event).where(Event.id == event_id, Event.user_id == user_id, Event.version == expected_version).returning(Event.id)).first()
    if result is None:
        db.rollback()
        return api_error(request, "stale_version", "This Pawprint changed since you opened it.", 412)
    db.commit()
    invalidate_user_analytics(user_id, propagated_request_id, settings)
    response.status_code = status.HTTP_204_NO_CONTENT
    return None
