import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.appointment import Appointment
    from app.models.employee_availability import EmployeeAvailability
    from app.models.employee_service import EmployeeService
    from app.models.location import Location
    from app.models.service import Service
    from app.models.tenant import Tenant
    from app.models.time_off import TimeOff
    from app.models.user import User


class Employee(Base):
    __tablename__ = "employees"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    location_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("locations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    first_name: Mapped[str] = mapped_column(String(100), nullable=False)
    last_name: Mapped[str] = mapped_column(String(100), nullable=False)
    email: Mapped[str | None] = mapped_column(String(255))
    phone: Mapped[str | None] = mapped_column(String(50))
    display_color: Mapped[str | None] = mapped_column(String(20))
    is_bookable: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    tenant: Mapped["Tenant"] = relationship(back_populates="employees")
    location: Mapped["Location"] = relationship(back_populates="employees")
    user: Mapped["User | None"] = relationship(back_populates="employees")
    employee_services: Mapped[list["EmployeeService"]] = relationship(
        back_populates="employee", cascade="all, delete-orphan", passive_deletes=True
    )
    services: Mapped[list["Service"]] = relationship(
        secondary="employee_services", back_populates="employees", viewonly=True
    )
    availabilities: Mapped[list["EmployeeAvailability"]] = relationship(
        back_populates="employee", cascade="all, delete-orphan", passive_deletes=True
    )
    time_off_entries: Mapped[list["TimeOff"]] = relationship(
        back_populates="employee", cascade="all, delete-orphan", passive_deletes=True
    )
    appointments: Mapped[list["Appointment"]] = relationship(back_populates="employee")
