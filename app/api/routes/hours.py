from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.orm import Session

from app.api.dependencies.tenant import HeaderTenantContext, require_header_roles
from app.core.database import get_database_session
from app.core.tenant_context import TenantContext
from app.models.membership import MembershipRole
from app.schemas.hours import (
    LocationClosureCreate,
    LocationClosureResponse,
    LocationClosureUpdate,
    OpeningHourCreate,
    OpeningHourResponse,
    OpeningHourUpdate,
)
from app.services.hours import LocationClosureService, OpeningHourService


router = APIRouter(prefix="/locations/{location_id}", tags=["Hours"])


def get_opening_hour_service(
    session: Annotated[Session, Depends(get_database_session)],
) -> OpeningHourService:
    return OpeningHourService(session)


def get_location_closure_service(
    session: Annotated[Session, Depends(get_database_session)],
) -> LocationClosureService:
    return LocationClosureService(session)


HoursWriteContext = Annotated[
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
    "/opening-hours",
    response_model=OpeningHourResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_opening_hour(
    location_id: UUID,
    payload: OpeningHourCreate,
    context: HoursWriteContext,
    service: Annotated[OpeningHourService, Depends(get_opening_hour_service)],
) -> OpeningHourResponse:
    return OpeningHourResponse.model_validate(service.create(context, location_id, payload))


@router.get("/opening-hours", response_model=list[OpeningHourResponse])
def list_opening_hours(
    location_id: UUID,
    context: HeaderTenantContext,
    service: Annotated[OpeningHourService, Depends(get_opening_hour_service)],
    is_active: bool | None = Query(default=True),
) -> list[OpeningHourResponse]:
    return [
        OpeningHourResponse.model_validate(item)
        for item in service.list_by_location(context, location_id, is_active=is_active)
    ]


@router.get("/opening-hours/{opening_hour_id}", response_model=OpeningHourResponse)
def get_opening_hour(
    location_id: UUID,
    opening_hour_id: UUID,
    context: HeaderTenantContext,
    service: Annotated[OpeningHourService, Depends(get_opening_hour_service)],
) -> OpeningHourResponse:
    return OpeningHourResponse.model_validate(
        service.get_by_id(context, location_id, opening_hour_id)
    )


@router.patch("/opening-hours/{opening_hour_id}", response_model=OpeningHourResponse)
def update_opening_hour(
    location_id: UUID,
    opening_hour_id: UUID,
    payload: OpeningHourUpdate,
    context: HoursWriteContext,
    service: Annotated[OpeningHourService, Depends(get_opening_hour_service)],
) -> OpeningHourResponse:
    return OpeningHourResponse.model_validate(
        service.update(context, location_id, opening_hour_id, payload)
    )


@router.delete("/opening-hours/{opening_hour_id}", response_model=OpeningHourResponse)
def deactivate_opening_hour(
    location_id: UUID,
    opening_hour_id: UUID,
    context: HoursWriteContext,
    service: Annotated[OpeningHourService, Depends(get_opening_hour_service)],
) -> OpeningHourResponse:
    return OpeningHourResponse.model_validate(
        service.deactivate(context, location_id, opening_hour_id)
    )


@router.post(
    "/closures",
    response_model=LocationClosureResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_location_closure(
    location_id: UUID,
    payload: LocationClosureCreate,
    context: HoursWriteContext,
    service: Annotated[LocationClosureService, Depends(get_location_closure_service)],
) -> LocationClosureResponse:
    return LocationClosureResponse.model_validate(service.create(context, location_id, payload))


@router.get("/closures", response_model=list[LocationClosureResponse])
def list_location_closures(
    location_id: UUID,
    context: HeaderTenantContext,
    service: Annotated[LocationClosureService, Depends(get_location_closure_service)],
) -> list[LocationClosureResponse]:
    return [
        LocationClosureResponse.model_validate(item)
        for item in service.list_by_location(context, location_id)
    ]


@router.get("/closures/{closure_id}", response_model=LocationClosureResponse)
def get_location_closure(
    location_id: UUID,
    closure_id: UUID,
    context: HeaderTenantContext,
    service: Annotated[LocationClosureService, Depends(get_location_closure_service)],
) -> LocationClosureResponse:
    return LocationClosureResponse.model_validate(
        service.get_by_id(context, location_id, closure_id)
    )


@router.patch("/closures/{closure_id}", response_model=LocationClosureResponse)
def update_location_closure(
    location_id: UUID,
    closure_id: UUID,
    payload: LocationClosureUpdate,
    context: HoursWriteContext,
    service: Annotated[LocationClosureService, Depends(get_location_closure_service)],
) -> LocationClosureResponse:
    return LocationClosureResponse.model_validate(
        service.update(context, location_id, closure_id, payload)
    )


@router.delete("/closures/{closure_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_location_closure(
    location_id: UUID,
    closure_id: UUID,
    context: HoursWriteContext,
    service: Annotated[LocationClosureService, Depends(get_location_closure_service)],
) -> Response:
    service.delete(context, location_id, closure_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
