from datetime import date, datetime, time
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


class PublicBusinessResponse(BaseModel):
    name: str
    slug: str


class PublicBookingSettingsResponse(BaseModel):
    enabled: bool
    default_location_id: UUID | None
    slot_interval_minutes: int
    minimum_notice_minutes: int
    maximum_advance_days: int
    require_phone: bool


class PublicBookingContextResponse(BaseModel):
    business: PublicBusinessResponse
    booking: PublicBookingSettingsResponse


class PublicOpeningHourResponse(BaseModel):
    weekday: int
    starts_at: time
    ends_at: time


class PublicLocationResponse(BaseModel):
    id: UUID
    name: str
    slug: str
    timezone: str
    address_line_1: str | None
    address_line_2: str | None
    postal_code: str | None
    city: str | None
    country_code: str
    opening_hours: list[PublicOpeningHourResponse]


class PublicServiceResponse(BaseModel):
    id: UUID
    location_id: UUID | None
    name: str
    description: str | None
    duration_minutes: int
    price_cents: int | None
    currency: str


class PublicEmployeeResponse(BaseModel):
    id: UUID
    display_name: str
    display_color: str | None


class PublicAvailabilitySlotResponse(BaseModel):
    employee_id: UUID
    service_id: UUID
    starts_at: datetime
    ends_at: datetime
    duration_minutes: int
    total_duration_minutes: int
    price_cents: int | None
    currency: str


class PublicAppointmentCustomerCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    first_name: str = Field(min_length=1, max_length=100)
    last_name: str = Field(min_length=1, max_length=100)
    email: EmailStr = Field(max_length=255)
    phone: str | None = Field(default=None, max_length=50)
    marketing_consent: bool = False

    @field_validator("first_name", "last_name", mode="before")
    @classmethod
    def strip_names(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value


class PublicAppointmentCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    location_id: UUID
    service_id: UUID
    employee_id: UUID
    starts_at: datetime
    customer: PublicAppointmentCustomerCreate
    customer_note: str | None = Field(default=None, max_length=1_000)

    @field_validator("starts_at")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("starts_at must include a timezone")
        return value


class PublicAppointmentLocationResponse(BaseModel):
    id: UUID
    name: str
    timezone: str


class PublicAppointmentEmployeeResponse(BaseModel):
    id: UUID
    display_name: str


class PublicAppointmentServiceResponse(BaseModel):
    id: UUID
    name: str
    duration_minutes: int
    price_cents: int | None
    currency: str


class PublicAppointmentResponse(BaseModel):
    booking_reference: str
    status: str
    location: PublicAppointmentLocationResponse
    employee: PublicAppointmentEmployeeResponse
    service: PublicAppointmentServiceResponse
    starts_at: datetime
    ends_at: datetime


class PublicAvailabilityQuery(BaseModel):
    location_id: UUID
    service_id: UUID
    date: date
    employee_id: UUID | None = None
