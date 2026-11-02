from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


def validate_bcrypt_password(password: str | None) -> str | None:
    if password is None:
        return None

    if len(password.encode("utf-8")) > 72:
        raise ValueError("Password must not exceed 72 UTF-8 bytes.")

    return password


class UserUpdate(BaseModel):
    email: EmailStr | None = None

    first_name: str | None = Field(
        default=None,
        min_length=1,
        max_length=100,
    )

    last_name: str | None = Field(
        default=None,
        min_length=1,
        max_length=100,
    )

    password: str | None = Field(
        default=None,
        min_length=12,
        max_length=128,
    )

    is_active: bool | None = None

    _validate_password = field_validator("password")(validate_bcrypt_password)

class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    email: EmailStr
    first_name: str
    last_name: str
    is_active: bool
    created_at: datetime
    updated_at: datetime
