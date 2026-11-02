import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.dialects.postgresql import ARRAY, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.location import Location
    from app.models.tenant import Tenant


class BookingSite(Base):
    __tablename__ = "booking_sites"
    __table_args__ = (
        CheckConstraint("slot_interval_minutes BETWEEN 5 AND 120", name="slot_interval_range"),
        CheckConstraint("minimum_notice_minutes >= 0", name="minimum_notice_nonnegative"),
        CheckConstraint("maximum_advance_days BETWEEN 1 AND 365", name="maximum_advance_range"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, unique=True, index=True
    )
    name: Mapped[str] = mapped_column(String(150), nullable=False, default="Site de réservation")
    publishable_key_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    key_prefix: Mapped[str] = mapped_column(String(24), nullable=False)
    allowed_origins: Mapped[list[str]] = mapped_column(
        ARRAY(String(255)), nullable=False, default=list, server_default="{}"
    )
    default_location_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("locations.id", ondelete="SET NULL"), nullable=True
    )
    slot_interval_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=15, server_default="15")
    minimum_notice_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=60, server_default="60")
    maximum_advance_days: Mapped[int] = mapped_column(Integer, nullable=False, default=90, server_default="90")
    require_phone: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    booking_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    tenant: Mapped["Tenant"] = relationship(back_populates="booking_site")
    default_location: Mapped["Location | None"] = relationship()
