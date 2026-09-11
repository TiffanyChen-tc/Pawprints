from __future__ import annotations

import re
from datetime import datetime, timezone
from uuid import UUID
from uuid import uuid4

from fastapi import APIRouter, Depends, Header, Request, Response, status
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.clients import invalidate_user_analytics
from app.config import Settings, get_settings
from app.db import get_db
from app.http import api_error, authenticated_user_id, etag, not_found, parse_if_match, request_id
from app.models import Category
from app.schemas import CategoryCreate, CategoryOut, CategoryUpdate


router = APIRouter(prefix="/api/v1/categories")


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def normalize_category_name(name: str) -> tuple[str, str]:
    display = re.sub(r"\s+", " ", name).strip()
    if display == "":
        raise ValueError("category name is required")
    if len(display) > 120:
        raise ValueError("category name is too long")
    return display, display.casefold()


def category_out(category: Category) -> dict:
    return CategoryOut.model_validate(category).model_dump(mode="json")


@router.get("")
def list_categories(request: Request, authorization: str | None = Header(default=None), db: Session = Depends(get_db), settings: Settings = Depends(get_settings)):
    user_id = authenticated_user_id(request, authorization, settings)
    if user_id is None:
        return api_error(request, "not_authenticated", "Authentication is required.", 401)
    categories = db.scalars(select(Category).where(Category.user_id == user_id).order_by(Category.name.asc())).all()
    return {"items": [category_out(category) for category in categories]}


@router.post("", status_code=status.HTTP_201_CREATED)
def create_category(payload: CategoryCreate, request: Request, response: Response, authorization: str | None = Header(default=None), db: Session = Depends(get_db), settings: Settings = Depends(get_settings)):
    user_id = authenticated_user_id(request, authorization, settings)
    if user_id is None:
        return api_error(request, "not_authenticated", "Authentication is required.", 401)
    try:
        name, normalized_name = normalize_category_name(payload.name)
    except ValueError:
        return api_error(request, "validation_failed", "Some fields are invalid.", 422)
    category = Category(id=uuid4(), user_id=user_id, name=name, normalized_name=normalized_name, version=1, created_at=now_utc(), updated_at=now_utc())
    db.add(category)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        return api_error(request, "category_name_exists", "Category name already exists.", 409)
    response.headers["ETag"] = etag(category.version)
    return category_out(category)


@router.patch("/{category_id}")
def rename_category(category_id: UUID, payload: CategoryUpdate, request: Request, response: Response, authorization: str | None = Header(default=None), if_match: str | None = Header(default=None), db: Session = Depends(get_db), settings: Settings = Depends(get_settings)):
    user_id = authenticated_user_id(request, authorization, settings)
    if user_id is None:
        return api_error(request, "not_authenticated", "Authentication is required.", 401)
    expected_version = parse_if_match(if_match)
    if expected_version is None:
        return api_error(request, "precondition_required", "If-Match is required.", 428)
    try:
        name, normalized_name = normalize_category_name(payload.name)
    except ValueError:
        return api_error(request, "validation_failed", "Some fields are invalid.", 422)

    existing = db.scalar(select(Category).where(Category.id == category_id, Category.user_id == user_id))
    if existing is None:
        return not_found(request)

    try:
        result = db.execute(
            update(Category)
            .where(Category.id == category_id, Category.user_id == user_id, Category.version == expected_version)
            .values(name=name, normalized_name=normalized_name, version=Category.version + 1, updated_at=now_utc())
            .returning(Category.id)
        ).first()
    except IntegrityError:
        db.rollback()
        return api_error(request, "category_name_exists", "Category name already exists.", 409)
    if result is None:
        db.rollback()
        return api_error(request, "stale_version", "This resource changed since you opened it.", 412)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        return api_error(request, "category_name_exists", "Category name already exists.", 409)
    updated = db.scalar(select(Category).where(Category.id == category_id, Category.user_id == user_id))
    response.headers["ETag"] = etag(updated.version)
    body = category_out(updated)
    db.rollback()
    invalidate_user_analytics(user_id, request_id(request), settings)
    return body
