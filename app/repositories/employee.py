from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.employee import Employee


class EmployeeRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get_by_id(self, tenant_id: UUID, employee_id: UUID) -> Employee | None:
        statement = select(Employee).where(
            Employee.id == employee_id,
            Employee.tenant_id == tenant_id,
        )
        return self.session.scalar(statement)

    def list_by_tenant(
        self,
        tenant_id: UUID,
        *,
        location_id: UUID | None = None,
        is_active: bool | None = True,
        is_bookable: bool | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[Employee], int]:
        conditions = [Employee.tenant_id == tenant_id]

        if location_id is not None:
            conditions.append(Employee.location_id == location_id)

        if is_active is not None:
            conditions.append(Employee.is_active.is_(is_active))

        if is_bookable is not None:
            conditions.append(Employee.is_bookable.is_(is_bookable))

        total = self.session.scalar(
            select(func.count()).select_from(Employee).where(*conditions)
        ) or 0
        statement = (
            select(Employee)
            .where(*conditions)
            .order_by(Employee.last_name.asc(), Employee.first_name.asc(), Employee.id.asc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        return list(self.session.scalars(statement)), total

    def add(self, employee: Employee) -> Employee:
        self.session.add(employee)
        self.session.flush()
        return employee
