from __future__ import annotations

from datetime import date
from typing import Literal
from uuid import UUID
import logging

from fastapi import APIRouter, Depends, Header, Request
from pydantic import BaseModel, ConfigDict, TypeAdapter, ValidationError
from redis.exceptions import RedisError
from sqlalchemy import text
from sqlalchemy.orm import Session

from pawprints_common.errors import error_response
from pawprints_common.jwt import JWTValidationError, verify_access_token
from pawprints_common.request_context import request_id_for

from app.cache import cache_key, get_cached_result, get_redis, get_user_cache_version, set_cached_result
from app.config import Settings, get_settings
from app.db import get_db


logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/analytics")


class ActivityQuery(BaseModel):
    start_date: date
    end_date: date
    category_id: UUID | None = None
    grouping: Literal["none", "week", "month"] = "none"


class CategoryActivityCount(BaseModel):
    model_config = ConfigDict(extra="forbid")

    category_id: UUID
    category_name: str
    count: int


class ActivityBucket(BaseModel):
    model_config = ConfigDict(extra="forbid")

    bucket_start_date: date
    items: list[CategoryActivityCount]


class UngroupedActivityCountsResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    start_date: date
    end_date: date
    grouping: Literal["none"]
    items: list[CategoryActivityCount]


class GroupedActivityCountsResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    start_date: date
    end_date: date
    grouping: Literal["week", "month"]
    buckets: list[ActivityBucket]


ActivityCountsResponse = UngroupedActivityCountsResponse | GroupedActivityCountsResponse
activity_counts_response_adapter = TypeAdapter(ActivityCountsResponse)


def api_error(request: Request, code: str, message: str, status_code: int):
    return error_response(code, message, status_code, request_id_for(request))


def authenticated_user_id(authorization: str | None, settings: Settings) -> UUID | None:
    if not authorization or not authorization.startswith("Bearer "):
        return None
    try:
        with open(settings.jwt_public_key_path, encoding="utf-8") as key_file:
            public_key = key_file.read()
        return verify_access_token(
            authorization.removeprefix("Bearer "),
            public_key,
            settings.jwt_issuer,
            settings.jwt_audience,
        ).user_id
    except (JWTValidationError, OSError):
        return None


def query_activity_counts(db: Session, user_id: UUID, query: ActivityQuery) -> dict:
    params: dict[str, object] = {
        "user_id": user_id,
        "start_date": query.start_date,
        "end_date": query.end_date,
    }
    category_clause = ""
    if query.category_id is not None:
        category_clause = " AND category_id = :category_id"
        params["category_id"] = query.category_id

    if query.grouping == "none":
        rows = db.execute(
            text(
                "SELECT category_id, category_name, CAST(count(*) AS integer) AS count "
                "FROM events.analytics_event_facts "
                "WHERE user_id = :user_id AND local_date BETWEEN :start_date AND :end_date"
                f"{category_clause} "
                "GROUP BY category_id, category_name "
                "ORDER BY category_name, category_id"
            ),
            params,
        ).mappings()
        return {
            "start_date": query.start_date.isoformat(),
            "end_date": query.end_date.isoformat(),
            "grouping": query.grouping,
            "items": [
                {
                    "category_id": str(row["category_id"]),
                    "category_name": row["category_name"],
                    "count": row["count"],
                }
                for row in rows
            ],
        }

    bucket_unit = "week" if query.grouping == "week" else "month"
    rows = db.execute(
        text(
            f"SELECT CAST(date_trunc('{bucket_unit}', local_date) AS date) AS bucket_start_date, "
            "category_id, category_name, CAST(count(*) AS integer) AS count "
            "FROM events.analytics_event_facts "
            "WHERE user_id = :user_id AND local_date BETWEEN :start_date AND :end_date"
            f"{category_clause} "
            "GROUP BY bucket_start_date, category_id, category_name "
            "ORDER BY bucket_start_date, category_name, category_id"
        ),
        params,
    ).mappings()
    buckets: list[dict] = []
    for row in rows:
        bucket_date = row["bucket_start_date"].isoformat()
        if not buckets or buckets[-1]["bucket_start_date"] != bucket_date:
            buckets.append({"bucket_start_date": bucket_date, "items": []})
        buckets[-1]["items"].append(
            {
                "category_id": str(row["category_id"]),
                "category_name": row["category_name"],
                "count": row["count"],
            }
        )
    return {
        "start_date": query.start_date.isoformat(),
        "end_date": query.end_date.isoformat(),
        "grouping": query.grouping,
        "buckets": buckets,
    }


@router.get("/activity-counts", response_model=ActivityCountsResponse)
def activity_counts(
    request: Request,
    query: ActivityQuery = Depends(),
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    if query.start_date > query.end_date:
        return api_error(request, "validation_failed", "Some fields are invalid.", 422)
    user_id = authenticated_user_id(authorization, settings)
    if user_id is None:
        response = api_error(request, "not_authenticated", "Authentication is required.", 401)
        response.headers["WWW-Authenticate"] = "Bearer"
        return response

    redis_client = get_redis()
    key: str | None = None
    try:
        version = get_user_cache_version(redis_client, user_id)
        key = cache_key(user_id, version, query)
        cached = get_cached_result(redis_client, key)
        if cached is not None:
            try:
                return activity_counts_response_adapter.validate_python(cached).model_dump(mode="json")
            except ValidationError:
                logger.warning(
                    "analytics cache payload invalid",
                    extra={"request_id": request_id_for(request)},
                )
    except (RedisError, ValueError):
        logger.warning("analytics cache read unavailable", extra={"request_id": request_id_for(request)})
        key = None

    result = query_activity_counts(db, user_id, query)
    if key is not None:
        try:
            set_cached_result(redis_client, key, result, settings.analytics_cache_ttl_seconds)
        except RedisError:
            logger.warning("analytics cache write unavailable", extra={"request_id": request_id_for(request)})
    return result
