import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Integer, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.employee import Employee
    from app.models.service import Service


class EmployeeService(Base):
    __tablename__ = "employee_services"
    __table_args__ = (
        CheckConstraint(
            "custom_duration_minutes IS NULL OR custom_duration_minutes > 0",
            name="custom_duration_minutes_positive",
        ),
        CheckConstraint(
            "custom_price_cents IS NULL OR custom_price_cents >= 0",
            name="custom_price_cents_nonnegative",
        ),
    )

    employee_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("employees.id", ondelete="CASCADE"), primary_key=True
    )
    service_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("services.id", ondelete="CASCADE"), primary_key=True
    )
    custom_duration_minutes: Mapped[int | None] = mapped_column(Integer)
    custom_price_cents: Mapped[int | None] = mapped_column(Integer)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())

    employee: Mapped["Employee"] = relationship(back_populates="employee_services")
    service: Mapped["Service"] = relationship(back_populates="employee_services")
