import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.appointment_service import AppointmentService
    from app.models.employee import Employee
    from app.models.employee_service import EmployeeService
    from app.models.location import Location
    from app.models.tenant import Tenant


class Service(Base):
    __tablename__ = "services"
    __table_args__ = (
        CheckConstraint("duration_minutes > 0", name="duration_minutes_positive"),
        CheckConstraint("buffer_before_minutes >= 0", name="buffer_before_minutes_nonnegative"),
        CheckConstraint("buffer_after_minutes >= 0", name="buffer_after_minutes_nonnegative"),
        CheckConstraint("price_cents IS NULL OR price_cents >= 0", name="price_cents_nonnegative"),
        CheckConstraint("length(currency) = 3", name="currency_length"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    location_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("locations.id", ondelete="CASCADE"), nullable=True, index=True
    )
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    duration_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    buffer_before_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    buffer_after_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    price_cents: Mapped[int | None] = mapped_column(Integer)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="EUR", server_default="EUR")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    tenant: Mapped["Tenant"] = relationship(back_populates="services")
    location: Mapped["Location | None"] = relationship(back_populates="services")
    employee_services: Mapped[list["EmployeeService"]] = relationship(
        back_populates="service", cascade="all, delete-orphan", passive_deletes=True
    )
    employees: Mapped[list["Employee"]] = relationship(
        secondary="employee_services", back_populates="services", viewonly=True
    )
    appointment_services: Mapped[list["AppointmentService"]] = relationship(back_populates="service")
