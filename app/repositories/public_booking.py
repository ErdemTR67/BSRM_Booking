from datetime import datetime
from uuid import UUID

from sqlalchemy import select, text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session, selectinload

from app.models.appointment import Appointment
from app.models.employee import Employee
from app.models.employee_availability import EmployeeAvailability
from app.models.employee_service import EmployeeService
from app.models.location import Location
from app.models.opening_hour import OpeningHour
from app.models.public_booking_idempotency import (
    PublicBookingIdempotency,
    PublicBookingRateLimit,
)
from app.models.service import Service
from app.models.tenant import Tenant


class PublicBookingRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get_tenant(self, tenant_id: UUID) -> Tenant | None:
        return self.session.scalar(select(Tenant).where(Tenant.id == tenant_id))

    def list_locations(self, tenant_id: UUID) -> list[Location]:
        statement = (
            select(Location)
            .options(selectinload(Location.opening_hours))
            .join(OpeningHour, OpeningHour.location_id == Location.id)
            .join(Employee, Employee.location_id == Location.id)
            .join(EmployeeAvailability, EmployeeAvailability.employee_id == Employee.id)
            .join(EmployeeService, EmployeeService.employee_id == Employee.id)
            .join(Service, Service.id == EmployeeService.service_id)
            .where(
                Location.tenant_id == tenant_id,
                Location.is_active.is_(True),
                OpeningHour.tenant_id == tenant_id,
                OpeningHour.is_active.is_(True),
                Employee.tenant_id == tenant_id,
                Employee.is_active.is_(True),
                Employee.is_bookable.is_(True),
                EmployeeAvailability.tenant_id == tenant_id,
                EmployeeAvailability.is_active.is_(True),
                EmployeeService.is_active.is_(True),
                Service.tenant_id == tenant_id,
                Service.is_active.is_(True),
                (Service.location_id.is_(None) | (Service.location_id == Location.id)),
            )
            .distinct()
            .order_by(Location.name.asc(), Location.id.asc())
        )
        return list(self.session.scalars(statement))

    def list_services(self, tenant_id: UUID, location_id: UUID) -> list[Service]:
        statement = (
            select(Service)
            .join(EmployeeService, EmployeeService.service_id == Service.id)
            .join(Employee, Employee.id == EmployeeService.employee_id)
            .where(
                Service.tenant_id == tenant_id,
                Service.is_active.is_(True),
                (Service.location_id.is_(None) | (Service.location_id == location_id)),
                Employee.tenant_id == tenant_id,
                Employee.location_id == location_id,
                Employee.is_active.is_(True),
                Employee.is_bookable.is_(True),
                EmployeeService.is_active.is_(True),
            )
            .distinct()
            .order_by(Service.name.asc(), Service.id.asc())
        )
        return list(self.session.scalars(statement))

    def list_employees(
        self, tenant_id: UUID, location_id: UUID, service_id: UUID
    ) -> list[Employee]:
        statement = (
            select(Employee)
            .join(EmployeeService, EmployeeService.employee_id == Employee.id)
            .join(Service, Service.id == EmployeeService.service_id)
            .where(
                Employee.tenant_id == tenant_id,
                Employee.location_id == location_id,
                Employee.is_active.is_(True),
                Employee.is_bookable.is_(True),
                EmployeeService.service_id == service_id,
                EmployeeService.is_active.is_(True),
                Service.tenant_id == tenant_id,
                Service.is_active.is_(True),
                (Service.location_id.is_(None) | (Service.location_id == location_id)),
            )
            .order_by(Employee.first_name.asc(), Employee.last_name.asc(), Employee.id.asc())
        )
        return list(self.session.scalars(statement))

    def get_service_option(
        self, tenant_id: UUID, location_id: UUID, service_id: UUID, employee_id: UUID
    ) -> tuple[Service, EmployeeService] | None:
        statement = (
            select(Service, EmployeeService)
            .join(EmployeeService, EmployeeService.service_id == Service.id)
            .join(Employee, Employee.id == EmployeeService.employee_id)
            .where(
                Service.tenant_id == tenant_id,
                Service.id == service_id,
                Service.is_active.is_(True),
                (Service.location_id.is_(None) | (Service.location_id == location_id)),
                Employee.id == employee_id,
                Employee.tenant_id == tenant_id,
                Employee.location_id == location_id,
                Employee.is_active.is_(True),
                Employee.is_bookable.is_(True),
                EmployeeService.is_active.is_(True),
            )
        )
        return self.session.execute(statement).tuples().one_or_none()

    def lock_idempotency_key(self, booking_site_id: UUID, idempotency_key: UUID) -> None:
        self.session.execute(
            text("SELECT pg_advisory_xact_lock(hashtextextended(:lock_key, 0))"),
            {"lock_key": f"{booking_site_id}:{idempotency_key}"},
        )

    def get_idempotency(
        self, booking_site_id: UUID, idempotency_key: UUID
    ) -> PublicBookingIdempotency | None:
        return self.session.scalar(
            select(PublicBookingIdempotency).where(
                PublicBookingIdempotency.booking_site_id == booking_site_id,
                PublicBookingIdempotency.idempotency_key == idempotency_key,
            )
        )

    def add_idempotency(self, entry: PublicBookingIdempotency) -> None:
        self.session.add(entry)
        self.session.flush()

    def get_appointment(self, tenant_id: UUID, appointment_id: UUID) -> Appointment | None:
        from app.models.appointment_service import AppointmentService

        return self.session.scalar(
            select(Appointment)
            .options(
                selectinload(Appointment.services).selectinload(AppointmentService.service),
                selectinload(Appointment.location),
                selectinload(Appointment.employee),
            )
            .where(Appointment.tenant_id == tenant_id, Appointment.id == appointment_id)
        )

    def increment_rate_limit(
        self,
        *,
        tenant_id: UUID,
        booking_site_id: UUID,
        client_hash: str,
        action: str,
        window_started_at: datetime,
    ) -> int:
        statement = (
            insert(PublicBookingRateLimit)
            .values(
                tenant_id=tenant_id,
                booking_site_id=booking_site_id,
                client_hash=client_hash,
                action=action,
                window_started_at=window_started_at,
                request_count=1,
            )
            .on_conflict_do_update(
                constraint="uq_public_booking_rate_limit_bucket",
                set_={"request_count": PublicBookingRateLimit.request_count + 1},
            )
            .returning(PublicBookingRateLimit.request_count)
        )
        return int(self.session.scalar(statement) or 0)
