from __future__ import annotations

import logging
from uuid import UUID

import httpx

from app.config import Settings


_client = httpx.Client(timeout=2.0)
logger = logging.getLogger(__name__)


def invalidate_user_analytics(user_id: UUID, request_id: str, settings: Settings) -> None:
    try:
        _client.post(
            f"{settings.analytics_service_url}/internal/analytics/users/{user_id}/invalidate",
            headers={
                "X-Pawprints-Internal-Service": "event",
                "X-Pawprints-Internal-Token": settings.event_internal_token,
                "X-Request-Id": request_id,
            },
        ).raise_for_status()
    except Exception:
        logger.info("analytics invalidation failed", extra={"request_id": request_id})
