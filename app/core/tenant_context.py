from dataclasses import dataclass
from uuid import UUID

from app.models.membership import MembershipRole


@dataclass(frozen=True)
class TenantContext:
    tenant_id: UUID
    user_id: UUID
    membership_id: UUID
    role: MembershipRole


@dataclass(frozen=True)
class PublicBookingContext:
    tenant_id: UUID
    booking_site_id: UUID
    origin: str | None
    allowed_origins: tuple[str, ...]
    default_location_id: UUID | None
    slot_interval_minutes: int
    minimum_notice_minutes: int
    maximum_advance_days: int
    require_phone: bool
