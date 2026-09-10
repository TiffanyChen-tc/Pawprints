from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


class EventValidationError(ValueError):
    pass


@dataclass(frozen=True)
class EventTime:
    occurred_at: datetime
    timezone: str
    local_date: date


def derive_event_time(local_datetime: str, timezone_name: str) -> EventTime:
    try:
        parsed = datetime.fromisoformat(local_datetime)
        zone = ZoneInfo(timezone_name)
    except (TypeError, ValueError, ZoneInfoNotFoundError) as exc:
        raise EventValidationError("invalid event time") from exc
    if parsed.tzinfo is not None:
        raise EventValidationError("local datetime must not include timezone")

    local = parsed.replace(tzinfo=zone)
    occurred_at = local.astimezone(timezone.utc)
    return EventTime(occurred_at=occurred_at, timezone=timezone_name, local_date=local.date())
