from __future__ import annotations

from functools import lru_cache
from hashlib import sha256
import json
from typing import Any
from uuid import UUID

from redis import Redis

from app.config import get_settings


def user_version_key(user_id: UUID) -> str:
    return f"analytics:user:{user_id}:version"


@lru_cache
def get_redis() -> Redis:
    return Redis.from_url(get_settings().redis_url, decode_responses=True)


def get_user_cache_version(redis_client: Redis, user_id: UUID) -> int:
    value = redis_client.get(user_version_key(user_id))
    return int(value) if value is not None else 0


def cache_key(user_id: UUID, version: int, query: Any) -> str:
    serialized = json.dumps(query.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))
    filter_hash = sha256(serialized.encode("utf-8")).hexdigest()
    return f"analytics:v1:user:{user_id}:ver:{version}:activity-counts:{filter_hash}"


def get_cached_result(redis_client: Redis, key: str) -> dict[str, Any] | None:
    value = redis_client.get(key)
    if value is None:
        return None
    try:
        result = json.loads(value)
    except (TypeError, json.JSONDecodeError):
        return None
    return result if isinstance(result, dict) else None


def set_cached_result(redis_client: Redis, key: str, result: dict[str, Any], ttl_seconds: int) -> None:
    redis_client.set(key, json.dumps(result, sort_keys=True, separators=(",", ":")), ex=ttl_seconds)


def invalidate_user(redis_client: Redis, user_id: UUID) -> None:
    redis_client.incr(user_version_key(user_id))
