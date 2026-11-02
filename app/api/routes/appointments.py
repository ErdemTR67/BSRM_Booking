from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.api.dependencies.tenant import HeaderTenantContext, require_header_roles
from app.core.database import get_database_session
from app.core.tenant_context import TenantContext
from app.models.appointment import AppointmentStatus
from app.models.membership import MembershipRole
from app.schemas.appointment import (
    AppointmentCancel,
    AppointmentCreate,
    AppointmentResponse,
    AppointmentUpdate,
)
from app.schemas.pagination import PageResponse
from app.services.appointment import AppointmentService


router = APIRouter(prefix="/appointments", tags=["Appointments"])


def get_appointment_service(
    session: Annotated[Session, Depends(get_database_session)],
) -> AppointmentService:
    return AppointmentService(session)


AppointmentWriteContext = Annotated[
    TenantContext,
    Depends(
        require_header_roles(
            MembershipRole.OWNER,
            MembershipRole.ADMIN,
            MembershipRole.MANAGER,
        )
    ),
]


@router.post("", response_model=AppointmentResponse, status_code=status.HTTP_201_CREATED)
def create_appointment(
    payload: AppointmentCreate,
    context: AppointmentWriteContext,
    service: Annotated[AppointmentService, Depends(get_appointment_service)],
) -> AppointmentResponse:
    return AppointmentResponse.model_validate(service.create(context, payload))


@router.get("", response_model=PageResponse[AppointmentResponse])
def list_appointments(
    context: HeaderTenantContext,
    service: Annotated[AppointmentService, Depends(get_appointment_service)],
    location_id: UUID | None = None,
    employee_id: UUID | None = None,
    customer_id: UUID | None = None,
    appointment_status: AppointmentStatus | None = Query(default=None, alias="status"),
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
) -> PageResponse[AppointmentResponse]:
    appointments, total = service.list_by_tenant(
        context,
        location_id=location_id,
        employee_id=employee_id,
        customer_id=customer_id,
        status=appointment_status,
        date_from=date_from,
        date_to=date_to,
        page=page,
        page_size=page_size,
    )
    return PageResponse(
        items=[AppointmentResponse.model_validate(item) for item in appointments],
        page=page,
        page_size=page_size,
        total=total,
    )


@router.get("/{appointment_id}", response_model=AppointmentResponse)
def get_appointment(
    appointment_id: UUID,
    context: HeaderTenantContext,
    service: Annotated[AppointmentService, Depends(get_appointment_service)],
) -> AppointmentResponse:
    return AppointmentResponse.model_validate(service.get_by_id(context, appointment_id))


@router.patch("/{appointment_id}", response_model=AppointmentResponse)
def update_appointment(
    appointment_id: UUID,
    payload: AppointmentUpdate,
    context: AppointmentWriteContext,
    service: Annotated[AppointmentService, Depends(get_appointment_service)],
) -> AppointmentResponse:
    return AppointmentResponse.model_validate(service.update(context, appointment_id, payload))


@router.post("/{appointment_id}/confirm", response_model=AppointmentResponse)
def confirm_appointment(
    appointment_id: UUID,
    context: AppointmentWriteContext,
    service: Annotated[AppointmentService, Depends(get_appointment_service)],
) -> AppointmentResponse:
    return AppointmentResponse.model_validate(
        service.transition(context, appointment_id, AppointmentStatus.CONFIRMED)
    )


@router.post("/{appointment_id}/cancel", response_model=AppointmentResponse)
def cancel_appointment(
    appointment_id: UUID,
    context: AppointmentWriteContext,
    service: Annotated[AppointmentService, Depends(get_appointment_service)],
    payload: AppointmentCancel | None = None,
) -> AppointmentResponse:
    return AppointmentResponse.model_validate(
        service.transition(
            context,
            appointment_id,
            AppointmentStatus.CANCELLED,
            cancellation_reason=payload.cancellation_reason if payload else None,
        )
    )


@router.post("/{appointment_id}/complete", response_model=AppointmentResponse)
def complete_appointment(
    appointment_id: UUID,
    context: AppointmentWriteContext,
    service: Annotated[AppointmentService, Depends(get_appointment_service)],
) -> AppointmentResponse:
    return AppointmentResponse.model_validate(
        service.transition(context, appointment_id, AppointmentStatus.COMPLETED)
    )


@router.post("/{appointment_id}/mark-no-show", response_model=AppointmentResponse)
def mark_appointment_no_show(
    appointment_id: UUID,
    context: AppointmentWriteContext,
    service: Annotated[AppointmentService, Depends(get_appointment_service)],
) -> AppointmentResponse:
    return AppointmentResponse.model_validate(
        service.transition(context, appointment_id, AppointmentStatus.NO_SHOW)
    )
