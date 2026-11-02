import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.models.appointment import Appointment
    from app.models.booking_site import BookingSite
    from app.models.customer import Customer
    from app.models.employee import Employee
    from app.models.employee_availability import EmployeeAvailability
    from app.models.location import Location
    from app.models.location_closure import LocationClosure
    from app.models.membership import Membership
    from app.models.opening_hour import OpeningHour
    from app.models.service import Service
    from app.models.time_off import TimeOff
    from app.models.tenant_invitation import TenantInvitation

class Tenant(Base):
    __tablename__ = "tenants"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    name: Mapped[str] = mapped_column(
        String(150),
        nullable=False,
    )

    slug: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        unique=True,
        index=True,
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default="true",
    )

    locations: Mapped[list["Location"]] = relationship(
        back_populates="tenant",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    memberships: Mapped[list["Membership"]] = relationship(
        back_populates="tenant", cascade="all, delete-orphan", passive_deletes=True
    )
    employees: Mapped[list["Employee"]] = relationship(
        back_populates="tenant", cascade="all, delete-orphan", passive_deletes=True
    )
    services: Mapped[list["Service"]] = relationship(
        back_populates="tenant", cascade="all, delete-orphan", passive_deletes=True
    )
    opening_hours: Mapped[list["OpeningHour"]] = relationship(
        back_populates="tenant", cascade="all, delete-orphan", passive_deletes=True
    )
    employee_availabilities: Mapped[list["EmployeeAvailability"]] = relationship(
        back_populates="tenant", cascade="all, delete-orphan", passive_deletes=True
    )
    time_off_entries: Mapped[list["TimeOff"]] = relationship(
        back_populates="tenant", cascade="all, delete-orphan", passive_deletes=True
    )
    location_closures: Mapped[list["LocationClosure"]] = relationship(
        back_populates="tenant", cascade="all, delete-orphan", passive_deletes=True
    )
    customers: Mapped[list["Customer"]] = relationship(
        back_populates="tenant", cascade="all, delete-orphan", passive_deletes=True
    )
    appointments: Mapped[list["Appointment"]] = relationship(
        back_populates="tenant", cascade="all, delete-orphan", passive_deletes=True
    )
    invitations: Mapped[list["TenantInvitation"]] = relationship(
        back_populates="tenant", cascade="all, delete-orphan", passive_deletes=True
    )
    booking_site: Mapped["BookingSite | None"] = relationship(
        back_populates="tenant", cascade="all, delete-orphan", passive_deletes=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    def __repr__(self) -> str:
        return f"Tenant(id={self.id!r}, slug={self.slug!r})"
