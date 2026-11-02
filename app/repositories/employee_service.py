from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.employee import Employee
from app.models.employee_service import EmployeeService
from app.models.service import Service


class EmployeeServiceRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get_by_ids(
        self,
        tenant_id: UUID,
        employee_id: UUID,
        service_id: UUID,
    ) -> EmployeeService | None:
        statement = (
            select(EmployeeService)
            .join(Employee, Employee.id == EmployeeService.employee_id)
            .join(Service, Service.id == EmployeeService.service_id)
            .where(
                EmployeeService.employee_id == employee_id,
                EmployeeService.service_id == service_id,
                Employee.tenant_id == tenant_id,
                Service.tenant_id == tenant_id,
            )
        )
        return self.session.scalar(statement)

    def list_by_employee(
        self,
        tenant_id: UUID,
        employee_id: UUID,
    ) -> list[EmployeeService]:
        statement = (
            select(EmployeeService)
            .join(Employee, Employee.id == EmployeeService.employee_id)
            .join(Service, Service.id == EmployeeService.service_id)
            .where(
                EmployeeService.employee_id == employee_id,
                Employee.tenant_id == tenant_id,
                Service.tenant_id == tenant_id,
            )
            .order_by(Service.name.asc())
        )
        return list(self.session.scalars(statement))

    def add(self, employee_service: EmployeeService) -> EmployeeService:
        self.session.add(employee_service)
        self.session.flush()
        return employee_service
