from __future__ import annotations

from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


MOODS = {"great", "good", "neutral", "low", "bad"}


class CategoryCreate(BaseModel):
    name: str


class CategoryUpdate(BaseModel):
    name: str


class CategoryOut(BaseModel):
    id: UUID
    name: str
    version: int

    model_config = ConfigDict(from_attributes=True)


class EventCreate(BaseModel):
    title: str = Field(max_length=120)
    category_id: UUID
    local_datetime: str
    timezone: str
    description: str | None = Field(default=None, max_length=10_000)
    mood: str | None = None
    location_name: str | None = None
    latitude: float | None = None
    longitude: float | None = None

    @model_validator(mode="after")
    def validate_invariants(self) -> EventCreate:
        validate_event_fields(self)
        return self


class EventPatch(BaseModel):
    title: str | None = Field(default=None, max_length=120)
    category_id: UUID | None = None
    local_datetime: str | None = None
    timezone: str | None = None
    description: str | None = Field(default=None, max_length=10_000)
    mood: str | None = None
    location_name: str | None = None
    latitude: float | None = None
    longitude: float | None = None

    @model_validator(mode="after")
    def validate_patch_fields(self) -> EventPatch:
        if self.title is not None and self.title.strip() == "":
            raise ValueError("title is required")
        if self.mood is not None and self.mood not in MOODS:
            raise ValueError("invalid mood")
        if (self.latitude is None) != (self.longitude is None):
            raise ValueError("latitude and longitude must be supplied together")
        if self.latitude is not None and not -90 <= self.latitude <= 90:
            raise ValueError("invalid latitude")
        if self.longitude is not None and not -180 <= self.longitude <= 180:
            raise ValueError("invalid longitude")
        return self


class EventOut(BaseModel):
    id: UUID
    category_id: UUID
    title: str
    description: str | None
    mood: str | None
    location_name: str | None
    latitude: float | None
    longitude: float | None
    occurred_at: datetime
    timezone: str
    local_date: date
    version: int
    category_name: str


def validate_event_fields(payload: EventCreate) -> None:
    if payload.title.strip() == "":
        raise ValueError("title is required")
    if payload.mood is not None and payload.mood not in MOODS:
        raise ValueError("invalid mood")
    if (payload.latitude is None) != (payload.longitude is None):
        raise ValueError("latitude and longitude must be supplied together")
    if payload.latitude is not None and not -90 <= payload.latitude <= 90:
        raise ValueError("invalid latitude")
    if payload.longitude is not None and not -180 <= payload.longitude <= 180:
        raise ValueError("invalid longitude")
