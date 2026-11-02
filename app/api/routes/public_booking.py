from datetime import date
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Query, Request, Response, status
from sqlalchemy.orm import Session

from app.api.dependencies.public_booking import CurrentPublicBookingContext
from app.core.database import get_database_session
from app.schemas.public_booking import (
    PublicAppointmentCreate,
    PublicAppointmentResponse,
    PublicAvailabilitySlotResponse,
    PublicBookingContextResponse,
    PublicEmployeeResponse,
    PublicLocationResponse,
    PublicServiceResponse,
)
from app.services.public_booking import PublicBookingService


router = APIRouter(prefix="/public/booking", tags=["Public booking"])


def get_public_booking_service(
    session: Annotated[Session, Depends(get_database_session)],
) -> PublicBookingService:
    return PublicBookingService(session)


def _remote_ip(request: Request) -> str | None:
    return request.client.host if request.client is not None else None


@router.get("/context", response_model=PublicBookingContextResponse)
def get_context(
    request: Request,
    context: CurrentPublicBookingContext,
    service: Annotated[PublicBookingService, Depends(get_public_booking_service)],
) -> PublicBookingContextResponse:
    service.check_rate_limit(context, remote_ip=_remote_ip(request), action="catalogue")
    return service.get_context(context)


@router.get("/locations", response_model=list[PublicLocationResponse])
def list_locations(
    request: Request,
    context: CurrentPublicBookingContext,
    service: Annotated[PublicBookingService, Depends(get_public_booking_service)],
) -> list[PublicLocationResponse]:
    service.check_rate_limit(context, remote_ip=_remote_ip(request), action="catalogue")
    return service.list_locations(context)


@router.get("/services", response_model=list[PublicServiceResponse])
def list_services(
    location_id: UUID,
    request: Request,
    context: CurrentPublicBookingContext,
    service: Annotated[PublicBookingService, Depends(get_public_booking_service)],
) -> list[PublicServiceResponse]:
    service.check_rate_limit(context, remote_ip=_remote_ip(request), action="catalogue")
    return service.list_services(context, location_id)


@router.get("/employees", response_model=list[PublicEmployeeResponse])
def list_employees(
    location_id: UUID,
    service_id: UUID,
    request: Request,
    context: CurrentPublicBookingContext,
    service: Annotated[PublicBookingService, Depends(get_public_booking_service)],
) -> list[PublicEmployeeResponse]:
    service.check_rate_limit(context, remote_ip=_remote_ip(request), action="catalogue")
    return service.list_employees(context, location_id, service_id)


@router.get("/availability", response_model=list[PublicAvailabilitySlotResponse])
def get_availability(
    location_id: UUID,
    service_id: UUID,
    request: Request,
    context: CurrentPublicBookingContext,
    service: Annotated[PublicBookingService, Depends(get_public_booking_service)],
    target_date: date = Query(alias="date"),
    employee_id: UUID | None = None,
) -> list[PublicAvailabilitySlotResponse]:
    service.check_rate_limit(context, remote_ip=_remote_ip(request), action="availability")
    return service.availability(
        context,
        location_id=location_id,
        service_id=service_id,
        target_date=target_date,
        employee_id=employee_id,
    )


@router.post(
    "/appointments",
    response_model=PublicAppointmentResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_appointment(
    payload: PublicAppointmentCreate,
    request: Request,
    response: Response,
    context: CurrentPublicBookingContext,
    service: Annotated[PublicBookingService, Depends(get_public_booking_service)],
    idempotency_key: Annotated[UUID, Header(alias="Idempotency-Key")],
    challenge_token: Annotated[str | None, Header(alias="X-Booking-Challenge")] = None,
) -> PublicAppointmentResponse:
    remote_ip = _remote_ip(request)
    service.check_rate_limit(context, remote_ip=remote_ip, action="create")
    result, created = service.create_appointment(
        context,
        payload,
        idempotency_key=idempotency_key,
        challenge_token=challenge_token,
        remote_ip=remote_ip,
    )
    if not created:
        response.status_code = status.HTTP_200_OK
    return result
