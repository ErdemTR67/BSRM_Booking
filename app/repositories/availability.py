from datetime import date, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.appointment import Appointment, AppointmentStatus
from app.models.employee import Employee
from app.models.employee_availability import EmployeeAvailability
from app.models.employee_service import EmployeeService
from app.models.location_closure import LocationClosure
from app.models.opening_hour import OpeningHour
from app.models.time_off import TimeOff, TimeOffStatus


class AvailabilityRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def list_eligible_employees(
        self,
        tenant_id: UUID,
        location_id: UUID,
        service_id: UUID,
        *,
        employee_id: UUID | None = None,
    ) -> list[tuple[Employee, EmployeeService]]:
        statement = (
            select(Employee, EmployeeService)
            .join(EmployeeService, EmployeeService.employee_id == Employee.id)
            .where(
                Employee.tenant_id == tenant_id,
                Employee.location_id == location_id,
                Employee.is_active.is_(True),
                Employee.is_bookable.is_(True),
                EmployeeService.service_id == service_id,
                EmployeeService.is_active.is_(True),
            )
            .order_by(Employee.last_name.asc(), Employee.first_name.asc())
        )
        if employee_id is not None:
            statement = statement.where(Employee.id == employee_id)
        return list(self.session.execute(statement).tuples())

    def list_opening_hours(
        self,
        tenant_id: UUID,
        location_id: UUID,
        weekday: int,
    ) -> list[OpeningHour]:
        statement = (
            select(OpeningHour)
            .where(
                OpeningHour.tenant_id == tenant_id,
                OpeningHour.location_id == location_id,
                OpeningHour.weekday == weekday,
                OpeningHour.is_active.is_(True),
            )
            .order_by(OpeningHour.starts_at.asc())
        )
        return list(self.session.scalars(statement))

    def list_closures(
        self,
        tenant_id: UUID,
        location_id: UUID,
        day_start: datetime,
        day_end: datetime,
    ) -> list[LocationClosure]:
        statement = select(LocationClosure).where(
            LocationClosure.tenant_id == tenant_id,
            LocationClosure.location_id == location_id,
            LocationClosure.starts_at < day_end,
            LocationClosure.ends_at > day_start,
        )
        return list(self.session.scalars(statement))

    def list_employee_availabilities(
        self,
        tenant_id: UUID,
        employee_ids: list[UUID],
        weekday: int,
        target_date: date,
    ) -> list[EmployeeAvailability]:
        if not employee_ids:
            return []
        statement = select(EmployeeAvailability).where(
            EmployeeAvailability.tenant_id == tenant_id,
            EmployeeAvailability.employee_id.in_(employee_ids),
            EmployeeAvailability.weekday == weekday,
            EmployeeAvailability.is_active.is_(True),
            (EmployeeAvailability.valid_from.is_(None))
            | (EmployeeAvailability.valid_from <= target_date),
            (EmployeeAvailability.valid_until.is_(None))
            | (EmployeeAvailability.valid_until >= target_date),
        )
        return list(self.session.scalars(statement))

    def list_approved_time_off(
        self,
        tenant_id: UUID,
        employee_ids: list[UUID],
        day_start: datetime,
        day_end: datetime,
    ) -> list[TimeOff]:
        if not employee_ids:
            return []
        statement = select(TimeOff).where(
            TimeOff.tenant_id == tenant_id,
            TimeOff.employee_id.in_(employee_ids),
            TimeOff.status == TimeOffStatus.APPROVED.value,
            TimeOff.starts_at < day_end,
            TimeOff.ends_at > day_start,
        )
        return list(self.session.scalars(statement))

    def list_active_appointments(
        self,
        tenant_id: UUID,
        employee_ids: list[UUID],
        day_start: datetime,
        day_end: datetime,
    ) -> list[Appointment]:
        if not employee_ids:
            return []
        statement = select(Appointment).where(
            Appointment.tenant_id == tenant_id,
            Appointment.employee_id.in_(employee_ids),
            Appointment.status.in_(
                [AppointmentStatus.PENDING.value, AppointmentStatus.CONFIRMED.value]
            ),
            Appointment.starts_at < day_end,
            Appointment.ends_at > day_start,
        )
        return list(self.session.scalars(statement))
