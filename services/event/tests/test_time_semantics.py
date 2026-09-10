from __future__ import annotations

import pytest

from app.time_semantics import EventValidationError, derive_event_time


def test_local_datetime_timezone_derives_utc_and_local_date():
    result = derive_event_time("2026-09-09T23:30:00", "Asia/Taipei")

    assert result.local_date.isoformat() == "2026-09-09"
    assert result.occurred_at.tzinfo is not None
    assert result.occurred_at.isoformat() == "2026-09-09T15:30:00+00:00"


def test_invalid_timezone_rejected():
    with pytest.raises(EventValidationError):
        derive_event_time("2026-09-09T12:00:00", "Not/AZone")
