from datetime import datetime, time
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class OpeningHourCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    weekday: int = Field(ge=0, le=6)
    starts_at: time
    ends_at: time

    @model_validator(mode="after")
    def validate_time_range(self) -> "OpeningHourCreate":
        if self.starts_at >= self.ends_at:
            raise ValueError("starts_at must be earlier than ends_at")
        return self


class OpeningHourUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    weekday: int | None = Field(default=None, ge=0, le=6)
    starts_at: time | None = None
    ends_at: time | None = None
    is_active: bool | None = None

    @model_validator(mode="after")
    def validate_complete_time_range(self) -> "OpeningHourUpdate":
        if (
            self.starts_at is not None
            and self.ends_at is not None
            and self.starts_at >= self.ends_at
        ):
            raise ValueError("starts_at must be earlier than ends_at")
        return self


class OpeningHourResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    location_id: UUID
    weekday: int
    starts_at: time
    ends_at: time
    is_active: bool
    created_at: datetime
    updated_at: datetime


class LocationClosureCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    starts_at: datetime
    ends_at: datetime
    reason: str | None = Field(default=None, max_length=255)

    @field_validator("starts_at", "ends_at")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        return _require_timezone(value)

    @model_validator(mode="after")
    def validate_time_range(self) -> "LocationClosureCreate":
        _validate_datetime_range(self.starts_at, self.ends_at)
        return self


class LocationClosureUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    starts_at: datetime | None = None
    ends_at: datetime | None = None
    reason: str | None = Field(default=None, max_length=255)

    @field_validator("starts_at", "ends_at")
    @classmethod
    def require_optional_timezone(cls, value: datetime | None) -> datetime | None:
        return _require_timezone(value) if value is not None else None

    @model_validator(mode="after")
    def validate_complete_time_range(self) -> "LocationClosureUpdate":
        if self.starts_at is not None and self.ends_at is not None:
            _validate_datetime_range(self.starts_at, self.ends_at)
        return self


class LocationClosureResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    location_id: UUID
    starts_at: datetime
    ends_at: datetime
    reason: str | None
    created_at: datetime
    updated_at: datetime


def _validate_datetime_range(starts_at: datetime, ends_at: datetime) -> None:
    if starts_at >= ends_at:
        raise ValueError("starts_at must be earlier than ends_at")


def _require_timezone(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("datetime values must include a timezone")
    return value
