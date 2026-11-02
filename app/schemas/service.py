from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ServiceCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    location_id: UUID | None = None
    name: str = Field(min_length=1, max_length=150)
    description: str | None = None
    duration_minutes: int = Field(gt=0)
    buffer_before_minutes: int = Field(default=0, ge=0)
    buffer_after_minutes: int = Field(default=0, ge=0)
    price_cents: int | None = Field(default=None, ge=0)
    currency: str = Field(default="EUR", min_length=3, max_length=3)

    @field_validator("name", mode="before")
    @classmethod
    def strip_name(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value

    @field_validator("currency")
    @classmethod
    def normalize_currency(cls, value: str) -> str:
        return value.upper()


class ServiceUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    location_id: UUID | None = None
    name: str | None = Field(default=None, min_length=1, max_length=150)
    description: str | None = None
    duration_minutes: int | None = Field(default=None, gt=0)
    buffer_before_minutes: int | None = Field(default=None, ge=0)
    buffer_after_minutes: int | None = Field(default=None, ge=0)
    price_cents: int | None = Field(default=None, ge=0)
    currency: str | None = Field(default=None, min_length=3, max_length=3)
    is_active: bool | None = None

    @field_validator("name", mode="before")
    @classmethod
    def strip_optional_name(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value

    @field_validator("currency")
    @classmethod
    def normalize_optional_currency(cls, value: str | None) -> str | None:
        return value.upper() if value is not None else None


class ServiceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    location_id: UUID | None
    name: str
    description: str | None
    duration_minutes: int
    buffer_before_minutes: int
    buffer_after_minutes: int
    price_cents: int | None
    currency: str
    is_active: bool
    created_at: datetime
    updated_at: datetime


class EmployeeServiceUpsert(BaseModel):
    model_config = ConfigDict(extra="forbid")

    custom_duration_minutes: int | None = Field(default=None, gt=0)
    custom_price_cents: int | None = Field(default=None, ge=0)
    is_active: bool = True


class EmployeeServiceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    employee_id: UUID
    service_id: UUID
    custom_duration_minutes: int | None
    custom_price_cents: int | None
    is_active: bool
    created_at: datetime
