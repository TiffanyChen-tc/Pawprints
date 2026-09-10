from __future__ import annotations

from uuid import UUID

import httpx

from app.config import Settings


class EventClient:
    def __init__(self, settings: Settings):
        self.settings = settings
        self._client = httpx.Client(timeout=5.0)

    def verify_ownership(self, event_id: UUID, authorization: str, request_id: str = "") -> bool:
        response = self._client.get(
            f"{self.settings.event_service_url}/internal/events/{event_id}/ownership",
            headers={
                "Authorization": authorization,
                "X-Request-Id": request_id,
                "X-Pawprints-Internal-Service": "media",
                "X-Pawprints-Internal-Token": self.settings.media_internal_token,
            },
        )
        if response.status_code == 200:
            return True
        if response.status_code in {401, 403, 404}:
            return False
        response.raise_for_status()
        return False
