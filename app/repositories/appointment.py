from datetime import datetime
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.models.appointment import Appointment, AppointmentStatus
from app.models.employee_service import EmployeeService
from app.models.service import Service


class AppointmentRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get_by_id(self, tenant_id: UUID, appointment_id: UUID) -> Appointment | None:
        statement = (
            select(Appointment)
            .options(selectinload(Appointment.services))
            .where(
                Appointment.id == appointment_id,
                Appointment.tenant_id == tenant_id,
            )
        )
        return self.session.scalar(statement)

    def list_by_tenant(
        self,
        tenant_id: UUID,
        *,
        location_id: UUID | None = None,
        employee_id: UUID | None = None,
        customer_id: UUID | None = None,
        status: AppointmentStatus | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[Appointment], int]:
        conditions = [Appointment.tenant_id == tenant_id]
        if location_id is not None:
            conditions.append(Appointment.location_id == location_id)
        if employee_id is not None:
            conditions.append(Appointment.employee_id == employee_id)
        if customer_id is not None:
            conditions.append(Appointment.customer_id == customer_id)
        if status is not None:
            conditions.append(Appointment.status == status.value)
        if date_from is not None:
            conditions.append(Appointment.starts_at >= date_from)
        if date_to is not None:
            conditions.append(Appointment.starts_at < date_to)
        total = self.session.scalar(
            select(func.count()).select_from(Appointment).where(*conditions)
        ) or 0
        statement = (
            select(Appointment)
            .options(selectinload(Appointment.services))
            .where(*conditions)
            .order_by(Appointment.starts_at.asc(), Appointment.id.asc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        return list(self.session.scalars(statement)), total

    def list_service_options(
        self,
        tenant_id: UUID,
        employee_id: UUID,
        service_ids: list[UUID],
    ) -> list[tuple[Service, EmployeeService]]:
        statement = (
            select(Service, EmployeeService)
            .join(EmployeeService, EmployeeService.service_id == Service.id)
            .where(
                Service.tenant_id == tenant_id,
                Service.id.in_(service_ids),
                Service.is_active.is_(True),
                EmployeeService.employee_id == employee_id,
                EmployeeService.is_active.is_(True),
            )
        )
        return list(self.session.execute(statement).tuples())

    def add(self, appointment: Appointment) -> Appointment:
        self.session.add(appointment)
        self.session.flush()
        return appointment
