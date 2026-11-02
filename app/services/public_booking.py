import hashlib
import json
import logging
from datetime import date, datetime, timedelta, timezone
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from urllib.parse import urlsplit

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.email import AppointmentConfirmationEmailSender
from app.core.exceptions import (
    AppointmentConflictError,
    AppointmentPersistenceError,
    AvailabilityCalculationError,
    EmployeeNotFoundError,
    LocationNotFoundError,
    PublicBookingIdempotencyConflictError,
    PublicBookingResourceNotFoundError,
    ServiceNotFoundError,
    TooManyRequestsError,
)
from app.core.tenant_context import PublicBookingContext
from app.core.turnstile import TurnstileVerifier
from app.models.appointment import Appointment
from app.models.location import Location
from app.models.public_booking_idempotency import PublicBookingIdempotency
from app.repositories.public_booking import PublicBookingRepository
from app.schemas.appointment import AppointmentCreate, AppointmentCustomerCreate
from app.schemas.public_booking import (
    PublicAppointmentCreate,
    PublicAppointmentEmployeeResponse,
    PublicAppointmentLocationResponse,
    PublicAppointmentResponse,
    PublicAppointmentServiceResponse,
    PublicAvailabilitySlotResponse,
    PublicBookingContextResponse,
    PublicBookingSettingsResponse,
    PublicBusinessResponse,
    PublicEmployeeResponse,
    PublicLocationResponse,
    PublicOpeningHourResponse,
    PublicServiceResponse,
)
from app.services.appointment import AppointmentService
from app.services.availability import AvailabilityService


logger = logging.getLogger(__name__)


class PublicBookingService:
    def __init__(
        self,
        session: Session,
        settings: Settings | None = None,
        challenge_verifier: TurnstileVerifier | None = None,
        email_sender: AppointmentConfirmationEmailSender | None = None,
    ) -> None:
        self.session = session
        self.settings = settings or get_settings()
        self.repository = PublicBookingRepository(session)
        self.availability_service = AvailabilityService(session)
        self.appointment_service = AppointmentService(session)
        self.challenge_verifier = challenge_verifier or TurnstileVerifier(self.settings)
        self.email_sender = email_sender or AppointmentConfirmationEmailSender(self.settings)

    def get_context(self, context: PublicBookingContext) -> PublicBookingContextResponse:
        tenant = self.repository.get_tenant(context.tenant_id)
        if tenant is None:
            raise LocationNotFoundError(context.default_location_id or UUID(int=0))
        return PublicBookingContextResponse(
            business=PublicBusinessResponse(name=tenant.name, slug=tenant.slug),
            booking=PublicBookingSettingsResponse(
                enabled=True,
                default_location_id=context.default_location_id,
                slot_interval_minutes=context.slot_interval_minutes,
                minimum_notice_minutes=context.minimum_notice_minutes,
                maximum_advance_days=context.maximum_advance_days,
                require_phone=context.require_phone,
            ),
        )

    def list_locations(self, context: PublicBookingContext) -> list[PublicLocationResponse]:
        result: list[PublicLocationResponse] = []
        for location in self.repository.list_locations(context.tenant_id):
            hours = sorted(
                (item for item in location.opening_hours if item.is_active),
                key=lambda item: (item.weekday, item.starts_at),
            )
            result.append(
                PublicLocationResponse(
                    id=location.id,
                    name=location.name,
                    slug=location.slug,
                    timezone=location.timezone,
                    address_line_1=location.address_line_1,
                    address_line_2=location.address_line_2,
                    postal_code=location.postal_code,
                    city=location.city,
                    country_code=location.country_code,
                    opening_hours=[
                        PublicOpeningHourResponse(
                            weekday=item.weekday,
                            starts_at=item.starts_at,
                            ends_at=item.ends_at,
                        )
                        for item in hours
                    ],
                )
            )
        return result

    def list_services(
        self, context: PublicBookingContext, location_id: UUID
    ) -> list[PublicServiceResponse]:
        self._ensure_location(context, location_id)
        return [
            PublicServiceResponse.model_validate(service, from_attributes=True)
            for service in self.repository.list_services(context.tenant_id, location_id)
        ]

    def list_employees(
        self, context: PublicBookingContext, location_id: UUID, service_id: UUID
    ) -> list[PublicEmployeeResponse]:
        self._ensure_location(context, location_id)
        services = self.repository.list_services(context.tenant_id, location_id)
        if not any(item.id == service_id for item in services):
            raise PublicBookingResourceNotFoundError()
        return [
            PublicEmployeeResponse(
                id=employee.id,
                display_name=f"{employee.first_name} {employee.last_name}".strip(),
                display_color=employee.display_color,
            )
            for employee in self.repository.list_employees(
                context.tenant_id, location_id, service_id
            )
        ]

    def availability(
        self,
        context: PublicBookingContext,
        *,
        location_id: UUID,
        service_id: UUID,
        target_date: date,
        employee_id: UUID | None,
    ) -> list[PublicAvailabilitySlotResponse]:
        location_timezone = self._get_location_timezone(context, location_id)
        today = datetime.now(location_timezone).date()
        if target_date < today or target_date > today + timedelta(days=context.maximum_advance_days):
            return []
        try:
            slots = self.availability_service.calculate(
                context,
                location_id=location_id,
                service_id=service_id,
                target_date=target_date,
                employee_id=employee_id,
                slot_interval_minutes=context.slot_interval_minutes,
            )
        except (LocationNotFoundError, ServiceNotFoundError, EmployeeNotFoundError) as error:
            raise PublicBookingResourceNotFoundError() from error
        earliest = datetime.now(timezone.utc) + timedelta(minutes=context.minimum_notice_minutes)
        result: list[PublicAvailabilitySlotResponse] = []
        for slot in slots:
            if slot.starts_at < earliest:
                continue
            option = self.repository.get_service_option(
                context.tenant_id,
                location_id,
                service_id,
                slot.employee_id,
            )
            if option is None:
                continue
            service, association = option
            price = (
                association.custom_price_cents
                if association.custom_price_cents is not None
                else service.price_cents
            )
            result.append(
                PublicAvailabilitySlotResponse(
                    employee_id=slot.employee_id,
                    service_id=slot.service_id,
                    starts_at=slot.starts_at,
                    ends_at=slot.ends_at,
                    duration_minutes=slot.duration_minutes,
                    total_duration_minutes=int(
                        (slot.ends_at - slot.starts_at).total_seconds() // 60
                    ),
                    price_cents=price,
                    currency=service.currency,
                )
            )
        return result

    def create_appointment(
        self,
        context: PublicBookingContext,
        payload: PublicAppointmentCreate,
        *,
        idempotency_key: UUID,
        challenge_token: str | None,
        remote_ip: str | None,
    ) -> tuple[PublicAppointmentResponse, bool]:
        request_hash = self._request_hash(payload)
        existing = self.repository.get_idempotency(context.booking_site_id, idempotency_key)
        if existing is not None:
            return self._replay(context, existing, request_hash), False

        self.session.commit()
        if context.require_phone and not payload.customer.phone:
            raise AppointmentPersistenceError("A phone number is required for this booking site.")
        now = datetime.now(timezone.utc)
        if payload.starts_at < now + timedelta(minutes=context.minimum_notice_minutes):
            raise AppointmentPersistenceError("The requested time does not satisfy the minimum notice.")
        self.challenge_verifier.verify(
            challenge_token,
            remote_ip=remote_ip,
            idempotency_key=idempotency_key,
            allowed_hostnames={
                hostname
                for origin in context.allowed_origins
                if (hostname := urlsplit(origin).hostname) is not None
            },
        )
        self.repository.lock_idempotency_key(context.booking_site_id, idempotency_key)
        existing = self.repository.get_idempotency(context.booking_site_id, idempotency_key)
        if existing is not None:
            return self._replay(context, existing, request_hash), False

        offered_slots = self.availability(
            context,
            location_id=payload.location_id,
            service_id=payload.service_id,
            target_date=payload.starts_at.astimezone(
                self._get_location_timezone(context, payload.location_id)
            ).date(),
            employee_id=payload.employee_id,
        )
        if not any(
            slot.employee_id == payload.employee_id and slot.starts_at == payload.starts_at
            for slot in offered_slots
        ):
            raise AppointmentConflictError()

        internal_payload = AppointmentCreate(
            location_id=payload.location_id,
            employee_id=payload.employee_id,
            service_ids=[payload.service_id],
            starts_at=payload.starts_at,
            customer=AppointmentCustomerCreate(
                first_name=payload.customer.first_name,
                last_name=payload.customer.last_name,
                email=payload.customer.email,
                phone=payload.customer.phone,
                marketing_consent=payload.customer.marketing_consent,
            ),
            notes=payload.customer_note,
        )
        public_reference = f"BSRM-{uuid4().hex[:12].upper()}"
        try:
            try:
                appointment = self.appointment_service.create(
                    context,
                    internal_payload,
                    commit=False,
                    public_reference=public_reference,
                )
            except (LocationNotFoundError, ServiceNotFoundError, EmployeeNotFoundError) as error:
                raise PublicBookingResourceNotFoundError() from error
            self.repository.add_idempotency(
                PublicBookingIdempotency(
                    tenant_id=context.tenant_id,
                    booking_site_id=context.booking_site_id,
                    idempotency_key=idempotency_key,
                    request_hash=request_hash,
                    appointment_id=appointment.id,
                )
            )
            self.session.commit()
        except IntegrityError as error:
            self.session.rollback()
            raise AppointmentPersistenceError() from error

        persisted = self.repository.get_appointment(context.tenant_id, appointment.id)
        if persisted is None:
            raise AppointmentPersistenceError()
        response = self._appointment_response(persisted)
        tenant = self.repository.get_tenant(context.tenant_id)
        try:
            self.email_sender.send_confirmation(
                recipient=str(payload.customer.email),
                customer_name=f"{payload.customer.first_name} {payload.customer.last_name}".strip(),
                reference=response.booking_reference,
                tenant_name=tenant.name if tenant is not None else "BSRM Booking",
                location_name=response.location.name,
                employee_name=response.employee.display_name,
                starts_at=response.starts_at,
                ends_at=response.ends_at,
                service_name=response.service.name,
                price_cents=response.service.price_cents,
                currency=response.service.currency,
            )
        except Exception as error:  # The booking is committed; delivery must not undo it.
            logger.warning(
                "Appointment confirmation delivery failed reference=%s type=%s",
                response.booking_reference,
                type(error).__name__,
            )
        return response, True

    def check_rate_limit(
        self, context: PublicBookingContext, *, remote_ip: str | None, action: str
    ) -> None:
        limits = {
            "catalogue": (self.settings.public_booking_catalogue_rate_limit, 60),
            "availability": (self.settings.public_booking_availability_rate_limit, 60),
            "create": (self.settings.public_booking_create_rate_limit, 600),
        }
        limit, window_seconds = limits[action]
        now = datetime.now(timezone.utc)
        epoch = int(now.timestamp())
        start = datetime.fromtimestamp(epoch - (epoch % window_seconds), timezone.utc)
        raw_client = remote_ip or "unknown"
        salt = self.settings.jwt_secret_key.get_secret_value()
        client_hash = hashlib.sha256(
            f"{salt}:{context.booking_site_id}:{raw_client}".encode("utf-8")
        ).hexdigest()
        count = self.repository.increment_rate_limit(
            tenant_id=context.tenant_id,
            booking_site_id=context.booking_site_id,
            client_hash=client_hash,
            action=action,
            window_started_at=start,
        )
        self.session.commit()
        if count > limit:
            retry_after = window_seconds - (epoch % window_seconds)
            raise TooManyRequestsError(retry_after)

    def _ensure_location(self, context: PublicBookingContext, location_id: UUID) -> None:
        self._get_location(context, location_id)

    def _get_location(
        self, context: PublicBookingContext, location_id: UUID
    ) -> Location:
        location = next(
            (
                item
                for item in self.repository.list_locations(context.tenant_id)
                if item.id == location_id
            ),
            None,
        )
        if location is None:
            raise PublicBookingResourceNotFoundError()
        return location

    def _get_location_timezone(
        self, context: PublicBookingContext, location_id: UUID
    ) -> ZoneInfo:
        location = self._get_location(context, location_id)
        try:
            return ZoneInfo(location.timezone)
        except ZoneInfoNotFoundError as error:
            raise AvailabilityCalculationError("Location timezone is invalid.") from error

    @staticmethod
    def _request_hash(payload: PublicAppointmentCreate) -> str:
        canonical = json.dumps(
            payload.model_dump(mode="json"), sort_keys=True, separators=(",", ":")
        )
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    def _replay(
        self,
        context: PublicBookingContext,
        existing: PublicBookingIdempotency,
        request_hash: str,
    ) -> PublicAppointmentResponse:
        if existing.request_hash != request_hash:
            raise PublicBookingIdempotencyConflictError()
        appointment = self.repository.get_appointment(
            context.tenant_id, existing.appointment_id
        )
        if appointment is None:
            raise AppointmentPersistenceError()
        return self._appointment_response(appointment)

    @staticmethod
    def _appointment_response(appointment: Appointment) -> PublicAppointmentResponse:
        snapshot = appointment.services[0]
        location_timezone = ZoneInfo(appointment.location.timezone)
        return PublicAppointmentResponse(
            booking_reference=appointment.public_reference or str(appointment.id),
            status=appointment.status,
            location=PublicAppointmentLocationResponse(
                id=appointment.location.id,
                name=appointment.location.name,
                timezone=appointment.location.timezone,
            ),
            employee=PublicAppointmentEmployeeResponse(
                id=appointment.employee.id,
                display_name=(
                    f"{appointment.employee.first_name} {appointment.employee.last_name}".strip()
                ),
            ),
            service=PublicAppointmentServiceResponse(
                id=snapshot.service_id,
                name=snapshot.service_name,
                duration_minutes=snapshot.duration_minutes,
                price_cents=snapshot.price_cents,
                currency=snapshot.service.currency,
            ),
            starts_at=appointment.starts_at.astimezone(location_timezone),
            ends_at=appointment.ends_at.astimezone(location_timezone),
        )
