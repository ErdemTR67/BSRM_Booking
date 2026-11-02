import uuid
from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.appointment_service import AppointmentService
    from app.models.customer import Customer
    from app.models.employee import Employee
    from app.models.location import Location
    from app.models.tenant import Tenant


class AppointmentStatus(str, Enum):
    PENDING = "pending"
    CONFIRMED = "confirmed"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    NO_SHOW = "no_show"


class Appointment(Base):
    __tablename__ = "appointments"
    __table_args__ = (
        CheckConstraint("starts_at < ends_at", name="time_range_valid"),
        CheckConstraint(
            "status IN ('pending', 'confirmed', 'completed', 'cancelled', 'no_show')",
            name="status_allowed",
        ),
        Index("ix_appointments_employee_id_starts_at", "employee_id", "starts_at"),
        Index("ix_appointments_location_id_starts_at", "location_id", "starts_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    public_reference: Mapped[str | None] = mapped_column(String(24), nullable=True, unique=True)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    location_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("locations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    employee_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("employees.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    customer_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("customers.id", ondelete="SET NULL"), nullable=True, index=True
    )
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    customer_name: Mapped[str] = mapped_column(String(201), nullable=False)
    customer_email: Mapped[str | None] = mapped_column(String(255))
    customer_phone: Mapped[str | None] = mapped_column(String(50))
    notes: Mapped[str | None] = mapped_column(Text)
    cancellation_reason: Mapped[str | None] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    tenant: Mapped["Tenant"] = relationship(back_populates="appointments")
    location: Mapped["Location"] = relationship(back_populates="appointments")
    employee: Mapped["Employee"] = relationship(back_populates="appointments")
    customer: Mapped["Customer | None"] = relationship(back_populates="appointments")
    services: Mapped[list["AppointmentService"]] = relationship(
        back_populates="appointment",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="AppointmentService.position",
    )
