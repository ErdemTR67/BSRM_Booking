from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class BookingSiteCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(default="Site de réservation", min_length=1, max_length=150)
    allowed_origins: list[str] = Field(min_length=1, max_length=20)
    default_location_id: UUID | None = None
    slot_interval_minutes: int = Field(default=15, ge=5, le=120)
    minimum_notice_minutes: int = Field(default=60, ge=0, le=43_200)
    maximum_advance_days: int = Field(default=90, ge=1, le=365)
    require_phone: bool = False
    booking_enabled: bool = True


class BookingSiteUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=1, max_length=150)
    allowed_origins: list[str] | None = Field(default=None, min_length=1, max_length=20)
    default_location_id: UUID | None = None
    slot_interval_minutes: int | None = Field(default=None, ge=5, le=120)
    minimum_notice_minutes: int | None = Field(default=None, ge=0, le=43_200)
    maximum_advance_days: int | None = Field(default=None, ge=1, le=365)
    require_phone: bool | None = None
    booking_enabled: bool | None = None


class BookingSiteResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    key_prefix: str
    allowed_origins: list[str]
    default_location_id: UUID | None
    slot_interval_minutes: int
    minimum_notice_minutes: int
    maximum_advance_days: int
    require_phone: bool
    booking_enabled: bool
    is_active: bool
    created_at: datetime
    updated_at: datetime


class BookingSiteIssuedResponse(BookingSiteResponse):
    publishable_key: str
