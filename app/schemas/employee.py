from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


class EmployeeCreate(BaseModel):
    location_id: UUID
    user_id: UUID | None = None
    first_name: str = Field(min_length=1, max_length=100)
    last_name: str = Field(min_length=1, max_length=100)
    email: EmailStr | None = Field(default=None, max_length=255)
    phone: str | None = Field(default=None, max_length=50)
    display_color: str | None = Field(default=None, max_length=20)
    is_bookable: bool = True

    @field_validator("first_name", "last_name", mode="before")
    @classmethod
    def strip_required_text(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value


class EmployeeUpdate(BaseModel):
    location_id: UUID | None = None
    user_id: UUID | None = None
    first_name: str | None = Field(default=None, min_length=1, max_length=100)
    last_name: str | None = Field(default=None, min_length=1, max_length=100)
    email: EmailStr | None = Field(default=None, max_length=255)
    phone: str | None = Field(default=None, max_length=50)
    display_color: str | None = Field(default=None, max_length=20)
    is_bookable: bool | None = None
    is_active: bool | None = None

    @field_validator("first_name", "last_name", mode="before")
    @classmethod
    def strip_optional_required_text(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value


class EmployeeResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    location_id: UUID
    user_id: UUID | None
    first_name: str
    last_name: str
    email: EmailStr | None
    phone: str | None
    display_color: str | None
    is_bookable: bool
    is_active: bool
    created_at: datetime
    updated_at: datetime
