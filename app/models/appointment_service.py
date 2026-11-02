import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.appointment import Appointment
    from app.models.service import Service


class AppointmentService(Base):
    __tablename__ = "appointment_services"
    __table_args__ = (
        UniqueConstraint("appointment_id", "position", name="uq_appointment_services_appointment_id_position"),
        CheckConstraint("duration_minutes > 0", name="duration_minutes_positive"),
        CheckConstraint("price_cents IS NULL OR price_cents >= 0", name="price_cents_nonnegative"),
        CheckConstraint("position >= 0", name="position_nonnegative"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    appointment_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("appointments.id", ondelete="CASCADE"), nullable=False
    )
    service_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("services.id", ondelete="RESTRICT"), nullable=False
    )
    service_name: Mapped[str] = mapped_column(String(150), nullable=False)
    duration_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    price_cents: Mapped[int | None] = mapped_column(Integer)
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())

    appointment: Mapped["Appointment"] = relationship(back_populates="services")
    service: Mapped["Service"] = relationship(back_populates="appointment_services")
