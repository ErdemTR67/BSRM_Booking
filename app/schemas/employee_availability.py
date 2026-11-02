from datetime import date, datetime, time
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.models.time_off import TimeOffStatus


class EmployeeAvailabilityCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    weekday: int = Field(ge=0, le=6)
    starts_at: time
    ends_at: time
    valid_from: date | None = None
    valid_until: date | None = None

    @model_validator(mode="after")
    def validate_ranges(self) -> "EmployeeAvailabilityCreate":
        _validate_availability_ranges(
            self.starts_at,
            self.ends_at,
            self.valid_from,
            self.valid_until,
        )
        return self


class EmployeeAvailabilityUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    weekday: int | None = Field(default=None, ge=0, le=6)
    starts_at: time | None = None
    ends_at: time | None = None
    valid_from: date | None = None
    valid_until: date | None = None
    is_active: bool | None = None

    @model_validator(mode="after")
    def validate_complete_ranges(self) -> "EmployeeAvailabilityUpdate":
        if self.starts_at is not None and self.ends_at is not None:
            if self.starts_at >= self.ends_at:
                raise ValueError("starts_at must be earlier than ends_at")
        if (
            self.valid_from is not None
            and self.valid_until is not None
            and self.valid_from > self.valid_until
        ):
            raise ValueError("valid_from must be earlier than or equal to valid_until")
        return self


class EmployeeAvailabilityResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    employee_id: UUID
    weekday: int
    starts_at: time
    ends_at: time
    valid_from: date | None
    valid_until: date | None
    is_active: bool
    created_at: datetime
    updated_at: datetime


class TimeOffCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    starts_at: datetime
    ends_at: datetime
    reason: str | None = Field(default=None, max_length=255)
    status: TimeOffStatus = TimeOffStatus.PENDING

    @field_validator("starts_at", "ends_at")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        return _require_timezone(value)

    @model_validator(mode="after")
    def validate_time_range(self) -> "TimeOffCreate":
        _validate_datetime_range(self.starts_at, self.ends_at)
        return self


class TimeOffUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    starts_at: datetime | None = None
    ends_at: datetime | None = None
    reason: str | None = Field(default=None, max_length=255)
    status: TimeOffStatus | None = None

    @field_validator("starts_at", "ends_at")
    @classmethod
    def require_optional_timezone(cls, value: datetime | None) -> datetime | None:
        return _require_timezone(value) if value is not None else None

    @model_validator(mode="after")
    def validate_complete_time_range(self) -> "TimeOffUpdate":
        if self.starts_at is not None and self.ends_at is not None:
            _validate_datetime_range(self.starts_at, self.ends_at)
        return self


class TimeOffResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    employee_id: UUID
    starts_at: datetime
    ends_at: datetime
    reason: str | None
    status: TimeOffStatus
    created_at: datetime
    updated_at: datetime


def _validate_availability_ranges(
    starts_at: time,
    ends_at: time,
    valid_from: date | None,
    valid_until: date | None,
) -> None:
    if starts_at >= ends_at:
        raise ValueError("starts_at must be earlier than ends_at")
    if valid_from is not None and valid_until is not None and valid_from > valid_until:
        raise ValueError("valid_from must be earlier than or equal to valid_until")


def _validate_datetime_range(starts_at: datetime, ends_at: datetime) -> None:
    if starts_at >= ends_at:
        raise ValueError("starts_at must be earlier than ends_at")


def _require_timezone(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("datetime values must include a timezone")
    return value
