from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.api.dependencies.tenant import CurrentTenantContext, require_roles
from app.core.database import get_database_session
from app.core.tenant_context import TenantContext
from app.models.membership import MembershipRole
from app.schemas.location import LocationCreate, LocationResponse, LocationUpdate
from app.services.location import LocationService


router = APIRouter(
    prefix="/tenants/{tenant_id}/locations",
    tags=["Locations"],
)


def get_location_service(
    session: Annotated[Session, Depends(get_database_session)],
) -> LocationService:
    return LocationService(session)


LocationWriteContext = Annotated[
    TenantContext,
    Depends(
        require_roles(
            MembershipRole.OWNER,
            MembershipRole.ADMIN,
            MembershipRole.MANAGER,
        )
    ),
]


@router.post(
    "",
    response_model=LocationResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_location(
    payload: LocationCreate,
    context: LocationWriteContext,
    service: Annotated[LocationService, Depends(get_location_service)],
) -> LocationResponse:
    location = service.create(tenant_id=context.tenant_id, payload=payload)
    return LocationResponse.model_validate(location)


@router.get("", response_model=list[LocationResponse])
def list_locations(
    context: CurrentTenantContext,
    service: Annotated[LocationService, Depends(get_location_service)],
    include_inactive: bool = Query(default=False),
) -> list[LocationResponse]:
    locations = service.list_by_tenant(
        tenant_id=context.tenant_id,
        include_inactive=include_inactive,
    )
    return [LocationResponse.model_validate(location) for location in locations]


@router.get("/{location_id}", response_model=LocationResponse)
def get_location(
    location_id: UUID,
    context: CurrentTenantContext,
    service: Annotated[LocationService, Depends(get_location_service)],
) -> LocationResponse:
    location = service.get_by_id(
        tenant_id=context.tenant_id,
        location_id=location_id,
    )
    return LocationResponse.model_validate(location)


@router.patch("/{location_id}", response_model=LocationResponse)
def update_location(
    location_id: UUID,
    payload: LocationUpdate,
    context: LocationWriteContext,
    service: Annotated[LocationService, Depends(get_location_service)],
) -> LocationResponse:
    location = service.update(
        tenant_id=context.tenant_id,
        location_id=location_id,
        payload=payload,
    )
    return LocationResponse.model_validate(location)


@router.delete("/{location_id}", response_model=LocationResponse)
def deactivate_location(
    location_id: UUID,
    context: LocationWriteContext,
    service: Annotated[LocationService, Depends(get_location_service)],
) -> LocationResponse:
    location = service.deactivate(
        tenant_id=context.tenant_id,
        location_id=location_id,
    )
    return LocationResponse.model_validate(location)
