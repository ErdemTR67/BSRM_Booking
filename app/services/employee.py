from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.exceptions import (
    EmployeeNotFoundError,
    EmployeePersistenceError,
    LocationNotFoundError,
    UserNotFoundError,
)
from app.core.tenant_context import TenantContext
from app.models.employee import Employee
from app.repositories.employee import EmployeeRepository
from app.repositories.location import LocationRepository
from app.repositories.membership import MembershipRepository
from app.repositories.user import UserRepository
from app.schemas.employee import EmployeeCreate, EmployeeUpdate


class EmployeeService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.repository = EmployeeRepository(session)
        self.location_repository = LocationRepository(session)
        self.membership_repository = MembershipRepository(session)
        self.user_repository = UserRepository(session)

    def create(self, context: TenantContext, payload: EmployeeCreate) -> Employee:
        self._validate_location(context.tenant_id, payload.location_id)
        self._validate_optional_user(context.tenant_id, payload.user_id)
        employee = Employee(
            tenant_id=context.tenant_id,
            location_id=payload.location_id,
            user_id=payload.user_id,
            first_name=payload.first_name,
            last_name=payload.last_name,
            email=str(payload.email).lower() if payload.email is not None else None,
            phone=payload.phone,
            display_color=payload.display_color,
            is_bookable=payload.is_bookable,
            is_active=True,
        )

        try:
            self.repository.add(employee)
            self.session.commit()
        except IntegrityError as error:
            self.session.rollback()
            raise EmployeePersistenceError() from error

        self.session.refresh(employee)
        return employee

    def get_by_id(self, context: TenantContext, employee_id: UUID) -> Employee:
        employee = self.repository.get_by_id(context.tenant_id, employee_id)

        if employee is None:
            raise EmployeeNotFoundError(employee_id)

        return employee

    def list_by_tenant(
        self,
        context: TenantContext,
        *,
        location_id: UUID | None = None,
        is_active: bool | None = True,
        is_bookable: bool | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[Employee], int]:
        if location_id is not None:
            self._validate_location(context.tenant_id, location_id)

        return self.repository.list_by_tenant(
            context.tenant_id,
            location_id=location_id,
            is_active=is_active,
            is_bookable=is_bookable,
            page=page,
            page_size=page_size,
        )

    def update(
        self,
        context: TenantContext,
        employee_id: UUID,
        payload: EmployeeUpdate,
    ) -> Employee:
        employee = self.get_by_id(context, employee_id)
        changes = payload.model_dump(exclude_unset=True)

        if "location_id" in changes:
            self._validate_location(context.tenant_id, changes["location_id"])

        if "user_id" in changes:
            self._validate_optional_user(context.tenant_id, changes["user_id"])

        if changes.get("email") is not None:
            changes["email"] = str(changes["email"]).lower()

        for field_name, value in changes.items():
            setattr(employee, field_name, value)

        self._commit(employee)
        return employee

    def deactivate(self, context: TenantContext, employee_id: UUID) -> Employee:
        employee = self.get_by_id(context, employee_id)
        employee.is_active = False
        self._commit(employee)
        return employee

    def _validate_location(self, tenant_id: UUID, location_id: UUID) -> None:
        location = self.location_repository.get_by_id(tenant_id, location_id)

        if location is None or not location.is_active:
            raise LocationNotFoundError(location_id)

    def _validate_optional_user(
        self,
        tenant_id: UUID,
        user_id: UUID | None,
    ) -> None:
        if user_id is None:
            return

        user = self.user_repository.get_by_id(user_id)
        membership = self.membership_repository.get_active_in_current_tenant(
            tenant_id,
            user_id,
        )

        if user is None or not user.is_active or membership is None:
            raise UserNotFoundError(user_id)

    def _commit(self, employee: Employee) -> None:
        try:
            self.session.commit()
        except IntegrityError as error:
            self.session.rollback()
            raise EmployeePersistenceError() from error

        self.session.refresh(employee)
