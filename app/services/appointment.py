from datetime import datetime, timedelta
from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.exceptions import (
    AppointmentConflictError,
    AppointmentNotFoundError,
    AppointmentPersistenceError,
    CustomerNotFoundError,
    EmployeeNotFoundError,
    InvalidAppointmentTransitionError,
    LocationNotFoundError,
    ServiceNotFoundError,
)
from app.core.tenant_context import PublicBookingContext, TenantContext
from app.models.appointment import Appointment, AppointmentStatus
from app.models.appointment_service import AppointmentService as AppointmentServiceModel
from app.models.customer import Customer
from app.repositories.appointment import AppointmentRepository
from app.repositories.customer import CustomerRepository
from app.repositories.employee import EmployeeRepository
from app.repositories.location import LocationRepository
from app.schemas.appointment import AppointmentCreate, AppointmentUpdate
from app.services.availability import AvailabilityService


class AppointmentService:
    _TRANSITIONS = {
        AppointmentStatus.PENDING: {
            AppointmentStatus.CONFIRMED,
            AppointmentStatus.CANCELLED,
        },
        AppointmentStatus.CONFIRMED: {
            AppointmentStatus.COMPLETED,
            AppointmentStatus.CANCELLED,
            AppointmentStatus.NO_SHOW,
        },
    }

    def __init__(self, session: Session) -> None:
        self.session = session
        self.repository = AppointmentRepository(session)
        self.location_repository = LocationRepository(session)
        self.employee_repository = EmployeeRepository(session)
        self.customer_repository = CustomerRepository(session)
        self.availability_service = AvailabilityService(session)

    def create(
        self,
        context: TenantContext | PublicBookingContext,
        payload: AppointmentCreate,
        *,
        commit: bool = True,
        public_reference: str | None = None,
    ) -> Appointment:
        location = self.location_repository.get_by_id(context.tenant_id, payload.location_id)
        if location is None or not location.is_active:
            raise LocationNotFoundError(payload.location_id)
        employee = self.employee_repository.get_by_id(context.tenant_id, payload.employee_id)
        if (
            employee is None
            or not employee.is_active
            or not employee.is_bookable
            or employee.location_id != payload.location_id
        ):
            raise EmployeeNotFoundError(payload.employee_id)

        options = self.repository.list_service_options(
            context.tenant_id,
            payload.employee_id,
            payload.service_ids,
        )
        options_by_id = {service.id: (service, association) for service, association in options}
        if len(options_by_id) != len(payload.service_ids):
            missing_id = next(
                service_id for service_id in payload.service_ids if service_id not in options_by_id
            )
            raise ServiceNotFoundError(missing_id)

        total_minutes = 0
        snapshots: list[AppointmentServiceModel] = []
        for position, service_id in enumerate(payload.service_ids):
            service, association = options_by_id[service_id]
            if service.location_id is not None and service.location_id != payload.location_id:
                raise ServiceNotFoundError(service_id)
            duration = association.custom_duration_minutes or service.duration_minutes
            price = (
                association.custom_price_cents
                if association.custom_price_cents is not None
                else service.price_cents
            )
            total_minutes += (
                service.buffer_before_minutes + duration + service.buffer_after_minutes
            )
            snapshots.append(
                AppointmentServiceModel(
                    service_id=service.id,
                    service_name=service.name,
                    duration_minutes=duration,
                    price_cents=price,
                    position=position,
                )
            )

        ends_at = payload.starts_at + timedelta(minutes=total_minutes)
        if not self.availability_service.is_employee_interval_available(
            context,
            location_id=payload.location_id,
            employee_id=payload.employee_id,
            starts_at=payload.starts_at,
            ends_at=ends_at,
        ):
            raise AppointmentConflictError()

        try:
            customer = self._resolve_customer(context, payload)
            appointment = Appointment(
                tenant_id=context.tenant_id,
                public_reference=public_reference,
                location_id=payload.location_id,
                employee_id=payload.employee_id,
                customer_id=customer.id,
                starts_at=payload.starts_at,
                ends_at=ends_at,
                status=AppointmentStatus.PENDING.value,
                customer_name=f"{customer.first_name} {customer.last_name}".strip(),
                customer_email=customer.email,
                customer_phone=customer.phone,
                notes=payload.notes,
                services=snapshots,
            )
            self.repository.add(appointment)
            if commit:
                self.session.commit()
        except IntegrityError as error:
            self.session.rollback()
            if self._is_overlap_violation(error):
                raise AppointmentConflictError() from error
            raise AppointmentPersistenceError() from error

        if commit:
            return self.get_by_id(context, appointment.id)
        return appointment

    def get_by_id(
        self, context: TenantContext | PublicBookingContext, appointment_id: UUID
    ) -> Appointment:
        appointment = self.repository.get_by_id(context.tenant_id, appointment_id)
        if appointment is None:
            raise AppointmentNotFoundError(appointment_id)
        return appointment

    def list_by_tenant(
        self,
        context: TenantContext | PublicBookingContext,
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
        self._validate_filter_dates(date_from, date_to)
        if location_id is not None and self.location_repository.get_by_id(
            context.tenant_id, location_id
        ) is None:
            raise LocationNotFoundError(location_id)
        if employee_id is not None and self.employee_repository.get_by_id(
            context.tenant_id, employee_id
        ) is None:
            raise EmployeeNotFoundError(employee_id)
        if customer_id is not None and self.customer_repository.get_by_id(
            context.tenant_id, customer_id
        ) is None:
            raise CustomerNotFoundError(customer_id)
        return self.repository.list_by_tenant(
            context.tenant_id,
            location_id=location_id,
            employee_id=employee_id,
            customer_id=customer_id,
            status=status,
            date_from=date_from,
            date_to=date_to,
            page=page,
            page_size=page_size,
        )

    def update(
        self,
        context: TenantContext,
        appointment_id: UUID,
        payload: AppointmentUpdate,
    ) -> Appointment:
        appointment = self.get_by_id(context, appointment_id)
        for field_name, value in payload.model_dump(exclude_unset=True).items():
            setattr(appointment, field_name, value)
        return self._save(context, appointment)

    def transition(
        self,
        context: TenantContext,
        appointment_id: UUID,
        target: AppointmentStatus,
        *,
        cancellation_reason: str | None = None,
    ) -> Appointment:
        appointment = self.get_by_id(context, appointment_id)
        current = AppointmentStatus(appointment.status)
        if target not in self._TRANSITIONS.get(current, set()):
            raise InvalidAppointmentTransitionError(current.value, target.value)
        appointment.status = target.value
        if target is AppointmentStatus.CANCELLED:
            appointment.cancellation_reason = cancellation_reason
        return self._save(context, appointment)

    def _resolve_customer(
        self,
        context: TenantContext | PublicBookingContext,
        payload: AppointmentCreate,
    ) -> Customer:
        if payload.customer_id is not None:
            customer = self.customer_repository.get_by_id(
                context.tenant_id, payload.customer_id
            )
            if customer is None:
                raise CustomerNotFoundError(payload.customer_id)
            return customer

        customer_data = payload.customer
        if customer_data is None:
            raise AppointmentPersistenceError("Customer information is required.")
        customer = Customer(
            tenant_id=context.tenant_id,
            first_name=customer_data.first_name,
            last_name=customer_data.last_name,
            email=str(customer_data.email).lower() if customer_data.email else None,
            phone=customer_data.phone,
            notes=customer_data.notes,
            marketing_consent=customer_data.marketing_consent,
        )
        self.customer_repository.add(customer)
        return customer

    @staticmethod
    def _validate_filter_dates(
        date_from: datetime | None,
        date_to: datetime | None,
    ) -> None:
        for value in (date_from, date_to):
            if value is not None and (value.tzinfo is None or value.utcoffset() is None):
                raise AppointmentPersistenceError("Date filters must include a timezone.")
        if date_from is not None and date_to is not None and date_from >= date_to:
            raise AppointmentPersistenceError("date_from must be earlier than date_to.")

    def _save(
        self,
        context: TenantContext,
        appointment: Appointment,
    ) -> Appointment:
        try:
            self.session.commit()
        except IntegrityError as error:
            self.session.rollback()
            if self._is_overlap_violation(error):
                raise AppointmentConflictError() from error
            raise AppointmentPersistenceError() from error
        return self.get_by_id(context, appointment.id)

    @staticmethod
    def _is_overlap_violation(error: IntegrityError) -> bool:
        diagnostic = getattr(getattr(error, "orig", None), "diag", None)
        return (
            getattr(diagnostic, "constraint_name", None)
            == "excl_appointments_employee_time_overlap"
        )
