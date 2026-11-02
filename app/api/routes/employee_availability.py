from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.api.dependencies.tenant import HeaderTenantContext, require_header_roles
from app.core.database import get_database_session
from app.core.tenant_context import TenantContext
from app.models.membership import MembershipRole
from app.models.time_off import TimeOffStatus
from app.schemas.employee_availability import (
    EmployeeAvailabilityCreate,
    EmployeeAvailabilityResponse,
    EmployeeAvailabilityUpdate,
    TimeOffCreate,
    TimeOffResponse,
    TimeOffUpdate,
)
from app.services.employee_availability import (
    EmployeeAvailabilityService,
    TimeOffService,
)


router = APIRouter(prefix="/employees/{employee_id}", tags=["Employee availability"])


def get_availability_service(
    session: Annotated[Session, Depends(get_database_session)],
) -> EmployeeAvailabilityService:
    return EmployeeAvailabilityService(session)


def get_time_off_service(
    session: Annotated[Session, Depends(get_database_session)],
) -> TimeOffService:
    return TimeOffService(session)


AvailabilityWriteContext = Annotated[
    TenantContext,
    Depends(
        require_header_roles(
            MembershipRole.OWNER,
            MembershipRole.ADMIN,
            MembershipRole.MANAGER,
        )
    ),
]


@router.post(
    "/availabilities",
    response_model=EmployeeAvailabilityResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_availability(
    employee_id: UUID,
    payload: EmployeeAvailabilityCreate,
    context: AvailabilityWriteContext,
    service: Annotated[EmployeeAvailabilityService, Depends(get_availability_service)],
) -> EmployeeAvailabilityResponse:
    return EmployeeAvailabilityResponse.model_validate(
        service.create(context, employee_id, payload)
    )


@router.get("/availabilities", response_model=list[EmployeeAvailabilityResponse])
def list_availabilities(
    employee_id: UUID,
    context: HeaderTenantContext,
    service: Annotated[EmployeeAvailabilityService, Depends(get_availability_service)],
    is_active: bool | None = Query(default=True),
) -> list[EmployeeAvailabilityResponse]:
    return [
        EmployeeAvailabilityResponse.model_validate(item)
        for item in service.list_by_employee(context, employee_id, is_active=is_active)
    ]


@router.get(
    "/availabilities/{availability_id}",
    response_model=EmployeeAvailabilityResponse,
)
def get_availability(
    employee_id: UUID,
    availability_id: UUID,
    context: HeaderTenantContext,
    service: Annotated[EmployeeAvailabilityService, Depends(get_availability_service)],
) -> EmployeeAvailabilityResponse:
    return EmployeeAvailabilityResponse.model_validate(
        service.get_by_id(context, employee_id, availability_id)
    )


@router.patch(
    "/availabilities/{availability_id}",
    response_model=EmployeeAvailabilityResponse,
)
def update_availability(
    employee_id: UUID,
    availability_id: UUID,
    payload: EmployeeAvailabilityUpdate,
    context: AvailabilityWriteContext,
    service: Annotated[EmployeeAvailabilityService, Depends(get_availability_service)],
) -> EmployeeAvailabilityResponse:
    return EmployeeAvailabilityResponse.model_validate(
        service.update(context, employee_id, availability_id, payload)
    )


@router.delete(
    "/availabilities/{availability_id}",
    response_model=EmployeeAvailabilityResponse,
)
def deactivate_availability(
    employee_id: UUID,
    availability_id: UUID,
    context: AvailabilityWriteContext,
    service: Annotated[EmployeeAvailabilityService, Depends(get_availability_service)],
) -> EmployeeAvailabilityResponse:
    return EmployeeAvailabilityResponse.model_validate(
        service.deactivate(context, employee_id, availability_id)
    )


@router.post(
    "/time-off",
    response_model=TimeOffResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_time_off(
    employee_id: UUID,
    payload: TimeOffCreate,
    context: AvailabilityWriteContext,
    service: Annotated[TimeOffService, Depends(get_time_off_service)],
) -> TimeOffResponse:
    return TimeOffResponse.model_validate(service.create(context, employee_id, payload))


@router.get("/time-off", response_model=list[TimeOffResponse])
def list_time_off(
    employee_id: UUID,
    context: HeaderTenantContext,
    service: Annotated[TimeOffService, Depends(get_time_off_service)],
    time_off_status: TimeOffStatus | None = Query(default=None, alias="status"),
) -> list[TimeOffResponse]:
    return [
        TimeOffResponse.model_validate(item)
        for item in service.list_by_employee(context, employee_id, status=time_off_status)
    ]


@router.get("/time-off/{time_off_id}", response_model=TimeOffResponse)
def get_time_off(
    employee_id: UUID,
    time_off_id: UUID,
    context: HeaderTenantContext,
    service: Annotated[TimeOffService, Depends(get_time_off_service)],
) -> TimeOffResponse:
    return TimeOffResponse.model_validate(
        service.get_by_id(context, employee_id, time_off_id)
    )


@router.patch("/time-off/{time_off_id}", response_model=TimeOffResponse)
def update_time_off(
    employee_id: UUID,
    time_off_id: UUID,
    payload: TimeOffUpdate,
    context: AvailabilityWriteContext,
    service: Annotated[TimeOffService, Depends(get_time_off_service)],
) -> TimeOffResponse:
    return TimeOffResponse.model_validate(
        service.update(context, employee_id, time_off_id, payload)
    )


@router.delete("/time-off/{time_off_id}", response_model=TimeOffResponse)
def cancel_time_off(
    employee_id: UUID,
    time_off_id: UUID,
    context: AvailabilityWriteContext,
    service: Annotated[TimeOffService, Depends(get_time_off_service)],
) -> TimeOffResponse:
    return TimeOffResponse.model_validate(
        service.cancel(context, employee_id, time_off_id)
    )
