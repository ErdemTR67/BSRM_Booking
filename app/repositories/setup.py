from dataclasses import dataclass
from datetime import date, time
from uuid import UUID

from sqlalchemy import exists, or_, select
from sqlalchemy.orm import Session

from app.models.employee import Employee
from app.models.employee_availability import EmployeeAvailability
from app.models.employee_service import EmployeeService
from app.models.location import Location
from app.models.opening_hour import OpeningHour
from app.models.service import Service


@dataclass(frozen=True, slots=True)
class ScheduleCandidate:
    opening_starts_at: time
    opening_ends_at: time
    availability_starts_at: time
    availability_ends_at: time
    duration_minutes: int
    buffer_before_minutes: int
    buffer_after_minutes: int


class SetupRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def has_active_location(self, tenant_id: UUID) -> bool:
        return self._exists(
            select(Location.id).where(
                Location.tenant_id == tenant_id,
                Location.is_active.is_(True),
            )
        )

    def has_active_opening_hour(self, tenant_id: UUID) -> bool:
        return self._exists(
            select(OpeningHour.id)
            .join(Location, Location.id == OpeningHour.location_id)
            .where(
                OpeningHour.tenant_id == tenant_id,
                Location.tenant_id == tenant_id,
                OpeningHour.is_active.is_(True),
                Location.is_active.is_(True),
            )
        )

    def has_active_service(self, tenant_id: UUID) -> bool:
        return self._exists(
            select(Service.id).where(
                Service.tenant_id == tenant_id,
                Service.is_active.is_(True),
            )
        )

    def has_bookable_employee(self, tenant_id: UUID) -> bool:
        return self._exists(
            select(Employee.id)
            .join(Location, Location.id == Employee.location_id)
            .where(
                Employee.tenant_id == tenant_id,
                Location.tenant_id == tenant_id,
                Employee.is_active.is_(True),
                Employee.is_bookable.is_(True),
                Location.is_active.is_(True),
            )
        )

    def has_active_employee_service(self, tenant_id: UUID) -> bool:
        return self._exists(
            self._employee_service_statement(tenant_id).with_only_columns(
                EmployeeService.employee_id
            )
        )

    def list_schedule_candidates(
        self,
        tenant_id: UUID,
        *,
        today: date,
    ) -> list[ScheduleCandidate]:
        statement = (
            select(
                OpeningHour.starts_at,
                OpeningHour.ends_at,
                EmployeeAvailability.starts_at,
                EmployeeAvailability.ends_at,
                EmployeeService.custom_duration_minutes,
                Service.duration_minutes,
                Service.buffer_before_minutes,
                Service.buffer_after_minutes,
            )
            .select_from(EmployeeAvailability)
            .join(Employee, Employee.id == EmployeeAvailability.employee_id)
            .join(Location, Location.id == Employee.location_id)
            .join(EmployeeService, EmployeeService.employee_id == Employee.id)
            .join(Service, Service.id == EmployeeService.service_id)
            .join(
                OpeningHour,
                (OpeningHour.location_id == Location.id)
                & (OpeningHour.weekday == EmployeeAvailability.weekday),
            )
            .where(
                EmployeeAvailability.tenant_id == tenant_id,
                Employee.tenant_id == tenant_id,
                Location.tenant_id == tenant_id,
                OpeningHour.tenant_id == tenant_id,
                Service.tenant_id == tenant_id,
                Location.is_active.is_(True),
                OpeningHour.is_active.is_(True),
                Employee.is_active.is_(True),
                Employee.is_bookable.is_(True),
                EmployeeService.is_active.is_(True),
                Service.is_active.is_(True),
                EmployeeAvailability.is_active.is_(True),
                or_(Service.location_id.is_(None), Service.location_id == Location.id),
                or_(
                    EmployeeAvailability.valid_until.is_(None),
                    EmployeeAvailability.valid_until >= today,
                ),
            )
        )
        rows = self.session.execute(statement).all()
        return [
            ScheduleCandidate(
                opening_starts_at=row[0],
                opening_ends_at=row[1],
                availability_starts_at=row[2],
                availability_ends_at=row[3],
                duration_minutes=row[4] or row[5],
                buffer_before_minutes=row[6],
                buffer_after_minutes=row[7],
            )
            for row in rows
        ]

    @staticmethod
    def _employee_service_statement(tenant_id: UUID):  # type: ignore[no-untyped-def]
        return (
            select(EmployeeService)
            .join(Employee, Employee.id == EmployeeService.employee_id)
            .join(Location, Location.id == Employee.location_id)
            .join(Service, Service.id == EmployeeService.service_id)
            .where(
                Employee.tenant_id == tenant_id,
                Location.tenant_id == tenant_id,
                Service.tenant_id == tenant_id,
                Employee.is_active.is_(True),
                Employee.is_bookable.is_(True),
                Location.is_active.is_(True),
                EmployeeService.is_active.is_(True),
                Service.is_active.is_(True),
                or_(Service.location_id.is_(None), Service.location_id == Location.id),
            )
        )

    def _exists(self, statement) -> bool:  # type: ignore[no-untyped-def]
        return bool(self.session.scalar(select(exists(statement))))
