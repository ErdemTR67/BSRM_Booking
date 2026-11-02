from datetime import date, time
from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.exceptions import (
    EmployeeAvailabilityNotFoundError,
    EmployeeAvailabilityPersistenceError,
    EmployeeNotFoundError,
    TimeOffNotFoundError,
    TimeOffPersistenceError,
)
from app.core.tenant_context import TenantContext
from app.models.employee import Employee
from app.models.employee_availability import EmployeeAvailability
from app.models.time_off import TimeOff, TimeOffStatus
from app.repositories.employee import EmployeeRepository
from app.repositories.employee_availability import EmployeeAvailabilityRepository
from app.repositories.time_off import TimeOffRepository
from app.schemas.employee_availability import (
    EmployeeAvailabilityCreate,
    EmployeeAvailabilityUpdate,
    TimeOffCreate,
    TimeOffUpdate,
)


class EmployeeAvailabilityService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.repository = EmployeeAvailabilityRepository(session)
        self.employee_repository = EmployeeRepository(session)

    def create(
        self,
        context: TenantContext,
        employee_id: UUID,
        payload: EmployeeAvailabilityCreate,
    ) -> EmployeeAvailability:
        self._get_employee(context.tenant_id, employee_id)
        availability = EmployeeAvailability(
            tenant_id=context.tenant_id,
            employee_id=employee_id,
            weekday=payload.weekday,
            starts_at=payload.starts_at,
            ends_at=payload.ends_at,
            valid_from=payload.valid_from,
            valid_until=payload.valid_until,
            is_active=True,
        )
        return self._save(availability, add=True)

    def get_by_id(
        self,
        context: TenantContext,
        employee_id: UUID,
        availability_id: UUID,
    ) -> EmployeeAvailability:
        self._get_employee(context.tenant_id, employee_id)
        availability = self.repository.get_by_id(
            context.tenant_id,
            employee_id,
            availability_id,
        )
        if availability is None:
            raise EmployeeAvailabilityNotFoundError(availability_id)
        return availability

    def list_by_employee(
        self,
        context: TenantContext,
        employee_id: UUID,
        *,
        is_active: bool | None = True,
    ) -> list[EmployeeAvailability]:
        self._get_employee(context.tenant_id, employee_id)
        return self.repository.list_by_employee(
            context.tenant_id,
            employee_id,
            is_active=is_active,
        )

    def update(
        self,
        context: TenantContext,
        employee_id: UUID,
        availability_id: UUID,
        payload: EmployeeAvailabilityUpdate,
    ) -> EmployeeAvailability:
        availability = self.get_by_id(context, employee_id, availability_id)
        changes = payload.model_dump(exclude_unset=True)
        starts_at = changes.get("starts_at", availability.starts_at)
        ends_at = changes.get("ends_at", availability.ends_at)
        valid_from = changes.get("valid_from", availability.valid_from)
        valid_until = changes.get("valid_until", availability.valid_until)
        self._validate_ranges(starts_at, ends_at, valid_from, valid_until)
        for field_name, value in changes.items():
            setattr(availability, field_name, value)
        return self._save(availability)

    def deactivate(
        self,
        context: TenantContext,
        employee_id: UUID,
        availability_id: UUID,
    ) -> EmployeeAvailability:
        availability = self.get_by_id(context, employee_id, availability_id)
        availability.is_active = False
        return self._save(availability)

    def _get_employee(self, tenant_id: UUID, employee_id: UUID) -> Employee:
        employee = self.employee_repository.get_by_id(tenant_id, employee_id)
        if employee is None:
            raise EmployeeNotFoundError(employee_id)
        return employee

    @staticmethod
    def _validate_ranges(
        starts_at: time,
        ends_at: time,
        valid_from: date | None,
        valid_until: date | None,
    ) -> None:
        if starts_at >= ends_at:
            raise EmployeeAvailabilityPersistenceError(
                "starts_at must be earlier than ends_at"
            )
        if valid_from is not None and valid_until is not None and valid_from > valid_until:
            raise EmployeeAvailabilityPersistenceError(
                "valid_from must be earlier than or equal to valid_until"
            )

    def _save(
        self,
        availability: EmployeeAvailability,
        *,
        add: bool = False,
    ) -> EmployeeAvailability:
        try:
            if add:
                self.repository.add(availability)
            self.session.commit()
        except IntegrityError as error:
            self.session.rollback()
            raise EmployeeAvailabilityPersistenceError() from error
        self.session.refresh(availability)
        return availability


class TimeOffService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.repository = TimeOffRepository(session)
        self.employee_repository = EmployeeRepository(session)

    def create(
        self,
        context: TenantContext,
        employee_id: UUID,
        payload: TimeOffCreate,
    ) -> TimeOff:
        self._get_employee(context.tenant_id, employee_id)
        time_off = TimeOff(
            tenant_id=context.tenant_id,
            employee_id=employee_id,
            starts_at=payload.starts_at,
            ends_at=payload.ends_at,
            reason=payload.reason,
            status=payload.status.value,
        )
        return self._save(time_off, add=True)

    def get_by_id(
        self,
        context: TenantContext,
        employee_id: UUID,
        time_off_id: UUID,
    ) -> TimeOff:
        self._get_employee(context.tenant_id, employee_id)
        time_off = self.repository.get_by_id(
            context.tenant_id,
            employee_id,
            time_off_id,
        )
        if time_off is None:
            raise TimeOffNotFoundError(time_off_id)
        return time_off

    def list_by_employee(
        self,
        context: TenantContext,
        employee_id: UUID,
        *,
        status: TimeOffStatus | None = None,
    ) -> list[TimeOff]:
        self._get_employee(context.tenant_id, employee_id)
        return self.repository.list_by_employee(
            context.tenant_id,
            employee_id,
            status=status,
        )

    def update(
        self,
        context: TenantContext,
        employee_id: UUID,
        time_off_id: UUID,
        payload: TimeOffUpdate,
    ) -> TimeOff:
        time_off = self.get_by_id(context, employee_id, time_off_id)
        changes = payload.model_dump(exclude_unset=True)
        starts_at = changes.get("starts_at", time_off.starts_at)
        ends_at = changes.get("ends_at", time_off.ends_at)
        if starts_at >= ends_at:
            raise TimeOffPersistenceError("starts_at must be earlier than ends_at")
        if "status" in changes:
            changes["status"] = changes["status"].value
        for field_name, value in changes.items():
            setattr(time_off, field_name, value)
        return self._save(time_off)

    def cancel(
        self,
        context: TenantContext,
        employee_id: UUID,
        time_off_id: UUID,
    ) -> TimeOff:
        time_off = self.get_by_id(context, employee_id, time_off_id)
        time_off.status = TimeOffStatus.CANCELLED.value
        return self._save(time_off)

    def _get_employee(self, tenant_id: UUID, employee_id: UUID) -> Employee:
        employee = self.employee_repository.get_by_id(tenant_id, employee_id)
        if employee is None:
            raise EmployeeNotFoundError(employee_id)
        return employee

    def _save(self, time_off: TimeOff, *, add: bool = False) -> TimeOff:
        try:
            if add:
                self.repository.add(time_off)
            self.session.commit()
        except IntegrityError as error:
            self.session.rollback()
            raise TimeOffPersistenceError() from error
        self.session.refresh(time_off)
        return time_off
