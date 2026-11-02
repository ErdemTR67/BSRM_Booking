from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.models.membership import MembershipRole


class MembershipResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tenant_id: UUID
    user_id: UUID
    role: MembershipRole
    is_active: bool
    created_at: datetime
    updated_at: datetime
