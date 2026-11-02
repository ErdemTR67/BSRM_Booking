import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.appointment import Appointment
    from app.models.employee import Employee
    from app.models.location_closure import LocationClosure
    from app.models.opening_hour import OpeningHour
    from app.models.service import Service
    from app.models.tenant import Tenant


class Location(Base):
    __tablename__ = "locations"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "slug",
            name="uq_locations_tenant_id_slug",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    name: Mapped[str] = mapped_column(
        String(150),
        nullable=False,
    )

    slug: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    timezone: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="Europe/Brussels",
        server_default="Europe/Brussels",
    )

    address_line_1: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    address_line_2: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    postal_code: Mapped[str | None] = mapped_column(
        String(20),
        nullable=True,
    )

    city: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    country_code: Mapped[str] = mapped_column(
        String(2),
        nullable=False,
        default="BE",
        server_default="BE",
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default="true",
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

    tenant: Mapped["Tenant"] = relationship(
        back_populates="locations",
    )

    employees: Mapped[list["Employee"]] = relationship(
        back_populates="location", cascade="all, delete-orphan", passive_deletes=True
    )
    services: Mapped[list["Service"]] = relationship(
        back_populates="location", passive_deletes=True
    )
    opening_hours: Mapped[list["OpeningHour"]] = relationship(
        back_populates="location", cascade="all, delete-orphan", passive_deletes=True
    )
    closures: Mapped[list["LocationClosure"]] = relationship(
        back_populates="location", cascade="all, delete-orphan", passive_deletes=True
    )
    appointments: Mapped[list["Appointment"]] = relationship(
        back_populates="location", cascade="all, delete-orphan", passive_deletes=True
    )
