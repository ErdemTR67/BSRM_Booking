from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator

from app.models.appointment import AppointmentStatus


class AppointmentCustomerCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    first_name: str = Field(min_length=1, max_length=100)
    last_name: str = Field(min_length=1, max_length=100)
    email: EmailStr | None = Field(default=None, max_length=255)
    phone: str | None = Field(default=None, max_length=50)
    notes: str | None = None
    marketing_consent: bool = False

    @field_validator("first_name", "last_name", mode="before")
    @classmethod
    def strip_names(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value


class AppointmentCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    location_id: UUID
    employee_id: UUID
    service_ids: list[UUID] = Field(min_length=1)
    starts_at: datetime
    customer_id: UUID | None = None
    customer: AppointmentCustomerCreate | None = None
    notes: str | None = None

    @field_validator("starts_at")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("starts_at must include a timezone")
        return value

    @field_validator("service_ids")
    @classmethod
    def require_distinct_services(cls, value: list[UUID]) -> list[UUID]:
        if len(value) != len(set(value)):
            raise ValueError("service_ids must not contain duplicates")
        return value

    @model_validator(mode="after")
    def validate_customer_source(self) -> "AppointmentCreate":
        if (self.customer_id is None) == (self.customer is None):
            raise ValueError("Provide exactly one of customer_id or customer")
        return self


class AppointmentUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    notes: str | None = None


class AppointmentCancel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    cancellation_reason: str | None = Field(default=None, max_length=255)


class AppointmentServiceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    service_id: UUID
    service_name: str
    duration_minutes: int
    price_cents: int | None
    position: int


class AppointmentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    location_id: UUID
    employee_id: UUID
    customer_id: UUID | None
    starts_at: datetime
    ends_at: datetime
    status: AppointmentStatus
    customer_name: str
    customer_email: EmailStr | None
    customer_phone: str | None
    notes: str | None
    cancellation_reason: str | None
    services: list[AppointmentServiceResponse]
    created_at: datetime
    updated_at: datetime
