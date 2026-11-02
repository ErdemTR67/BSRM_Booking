from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.exceptions import (
    EmployeeNotFoundError,
    EmployeeServiceNotFoundError,
    EmployeeServicePersistenceError,
    ServiceNotFoundError,
)
from app.core.tenant_context import TenantContext
from app.models.employee import Employee
from app.models.employee_service import EmployeeService
from app.models.service import Service
from app.repositories.employee import EmployeeRepository
from app.repositories.employee_service import EmployeeServiceRepository
from app.repositories.service import ServiceRepository
from app.schemas.service import EmployeeServiceUpsert


class EmployeeServiceService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.repository = EmployeeServiceRepository(session)
        self.employee_repository = EmployeeRepository(session)
        self.service_repository = ServiceRepository(session)

    def upsert(
        self,
        context: TenantContext,
        employee_id: UUID,
        service_id: UUID,
        payload: EmployeeServiceUpsert,
    ) -> EmployeeService:
        self._get_employee(context.tenant_id, employee_id)
        self._get_service(context.tenant_id, service_id)
        employee_service = self.repository.get_by_ids(
            context.tenant_id,
            employee_id,
            service_id,
        )

        is_new = employee_service is None

        if is_new:
            employee_service = EmployeeService(
                employee_id=employee_id,
                service_id=service_id,
            )

        employee_service.custom_duration_minutes = payload.custom_duration_minutes
        employee_service.custom_price_cents = payload.custom_price_cents
        employee_service.is_active = payload.is_active

        try:
            if is_new:
                self.repository.add(employee_service)

            self.session.commit()
        except IntegrityError as error:
            self.session.rollback()
            raise EmployeeServicePersistenceError() from error

        self.session.refresh(employee_service)
        return employee_service

    def list_by_employee(
        self,
        context: TenantContext,
        employee_id: UUID,
    ) -> list[EmployeeService]:
        self._get_employee(context.tenant_id, employee_id)
        return self.repository.list_by_employee(context.tenant_id, employee_id)

    def deactivate(
        self,
        context: TenantContext,
        employee_id: UUID,
        service_id: UUID,
    ) -> EmployeeService:
        self._get_employee(context.tenant_id, employee_id)
        self._get_service(context.tenant_id, service_id)
        employee_service = self.repository.get_by_ids(
            context.tenant_id,
            employee_id,
            service_id,
        )

        if employee_service is None:
            raise EmployeeServiceNotFoundError()

        employee_service.is_active = False
        self._commit(employee_service)
        return employee_service

    def _get_employee(self, tenant_id: UUID, employee_id: UUID) -> Employee:
        employee = self.employee_repository.get_by_id(tenant_id, employee_id)

        if employee is None:
            raise EmployeeNotFoundError(employee_id)

        return employee

    def _get_service(self, tenant_id: UUID, service_id: UUID) -> Service:
        service = self.service_repository.get_by_id(tenant_id, service_id)

        if service is None:
            raise ServiceNotFoundError(service_id)

        return service

    def _commit(self, employee_service: EmployeeService) -> None:
        try:
            self.session.commit()
        except IntegrityError as error:
            self.session.rollback()
            raise EmployeeServicePersistenceError() from error

        self.session.refresh(employee_service)
