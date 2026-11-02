from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.employee_availability import EmployeeAvailability


class EmployeeAvailabilityRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get_by_id(
        self,
        tenant_id: UUID,
        employee_id: UUID,
        availability_id: UUID,
    ) -> EmployeeAvailability | None:
        statement = select(EmployeeAvailability).where(
            EmployeeAvailability.id == availability_id,
            EmployeeAvailability.tenant_id == tenant_id,
            EmployeeAvailability.employee_id == employee_id,
        )
        return self.session.scalar(statement)

    def list_by_employee(
        self,
        tenant_id: UUID,
        employee_id: UUID,
        *,
        is_active: bool | None = True,
    ) -> list[EmployeeAvailability]:
        statement = select(EmployeeAvailability).where(
            EmployeeAvailability.tenant_id == tenant_id,
            EmployeeAvailability.employee_id == employee_id,
        )
        if is_active is not None:
            statement = statement.where(EmployeeAvailability.is_active.is_(is_active))
        statement = statement.order_by(
            EmployeeAvailability.weekday.asc(),
            EmployeeAvailability.starts_at.asc(),
        )
        return list(self.session.scalars(statement))

    def add(self, availability: EmployeeAvailability) -> EmployeeAvailability:
        self.session.add(availability)
        self.session.flush()
        return availability
