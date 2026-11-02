from datetime import datetime
from enum import Enum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.models.membership import MembershipRole
from app.schemas.user import validate_bcrypt_password


class InvitationStatus(str, Enum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    REVOKED = "revoked"
    EXPIRED = "expired"


class TenantInvitationCreate(BaseModel):
    email: EmailStr
    role: MembershipRole = MembershipRole.OWNER


class TenantInvitationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tenant_id: UUID
    email: EmailStr
    role: MembershipRole
    status: InvitationStatus
    expires_at: datetime
    accepted_at: datetime | None
    revoked_at: datetime | None
    sent_at: datetime | None
    created_at: datetime
    acceptance_url: str | None = None


class InvitationTokenRequest(BaseModel):
    token: str = Field(min_length=32, max_length=512)


class InvitationAcceptRequest(InvitationTokenRequest):
    password: str = Field(min_length=12, max_length=128)
    first_name: str = Field(min_length=1, max_length=100)
    last_name: str = Field(min_length=1, max_length=100)

    _validate_password = field_validator("password")(validate_bcrypt_password)


class InvitationPreviewResponse(BaseModel):
    tenant_name: str
    email: EmailStr
    role: MembershipRole
    expires_at: datetime
