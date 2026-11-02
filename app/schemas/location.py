from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class LocationCreate(BaseModel):
    name: str = Field(min_length=2, max_length=150)

    slug: str = Field(
        min_length=2,
        max_length=100,
        pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$",
    )

    timezone: str = Field(
        default="Europe/Brussels",
        min_length=1,
        max_length=50,
    )

    address_line_1: str | None = Field(
        default=None,
        max_length=255,
    )

    address_line_2: str | None = Field(
        default=None,
        max_length=255,
    )

    postal_code: str | None = Field(
        default=None,
        max_length=20,
    )

    city: str | None = Field(
        default=None,
        max_length=100,
    )

    country_code: str = Field(
        default="BE",
        min_length=2,
        max_length=2,
    )


class LocationUpdate(BaseModel):
    name: str | None = Field(
        default=None,
        min_length=2,
        max_length=150,
    )

    slug: str | None = Field(
        default=None,
        min_length=2,
        max_length=100,
        pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$",
    )

    timezone: str | None = Field(
        default=None,
        min_length=1,
        max_length=50,
    )

    address_line_1: str | None = Field(
        default=None,
        max_length=255,
    )

    address_line_2: str | None = Field(
        default=None,
        max_length=255,
    )

    postal_code: str | None = Field(
        default=None,
        max_length=20,
    )

    city: str | None = Field(
        default=None,
        max_length=100,
    )

    country_code: str | None = Field(
        default=None,
        min_length=2,
        max_length=2,
    )

    is_active: bool | None = None


class LocationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tenant_id: UUID
    name: str
    slug: str
    timezone: str
    address_line_1: str | None
    address_line_2: str | None
    postal_code: str | None
    city: str | None
    country_code: str
    is_active: bool
    created_at: datetime
    updated_at: datetime