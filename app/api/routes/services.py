from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.api.dependencies.tenant import HeaderTenantContext, require_header_roles
from app.core.database import get_database_session
from app.core.tenant_context import TenantContext
from app.models.membership import MembershipRole
from app.schemas.pagination import PageResponse
from app.schemas.service import ServiceCreate, ServiceResponse, ServiceUpdate
from app.services.service import ServiceService


router = APIRouter(prefix="/services", tags=["Services"])


def get_service_service(
    session: Annotated[Session, Depends(get_database_session)],
) -> ServiceService:
    return ServiceService(session)


ServiceWriteContext = Annotated[
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
    "",
    response_model=ServiceResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_service(
    payload: ServiceCreate,
    context: ServiceWriteContext,
    service: Annotated[ServiceService, Depends(get_service_service)],
) -> ServiceResponse:
    result = service.create(context, payload)
    return ServiceResponse.model_validate(result)


@router.get("", response_model=PageResponse[ServiceResponse])
def list_services(
    context: HeaderTenantContext,
    service: Annotated[ServiceService, Depends(get_service_service)],
    is_active: bool | None = Query(default=True),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
) -> PageResponse[ServiceResponse]:
    results, total = service.list_by_tenant(
        context,
        is_active=is_active,
        page=page,
        page_size=page_size,
    )
    return PageResponse(
        items=[ServiceResponse.model_validate(item) for item in results],
        page=page,
        page_size=page_size,
        total=total,
    )


@router.get("/{service_id}", response_model=ServiceResponse)
def get_service(
    service_id: UUID,
    context: HeaderTenantContext,
    service: Annotated[ServiceService, Depends(get_service_service)],
) -> ServiceResponse:
    result = service.get_by_id(context, service_id)
    return ServiceResponse.model_validate(result)


@router.patch("/{service_id}", response_model=ServiceResponse)
def update_service(
    service_id: UUID,
    payload: ServiceUpdate,
    context: ServiceWriteContext,
    service: Annotated[ServiceService, Depends(get_service_service)],
) -> ServiceResponse:
    result = service.update(context, service_id, payload)
    return ServiceResponse.model_validate(result)


@router.delete("/{service_id}", response_model=ServiceResponse)
def deactivate_service(
    service_id: UUID,
    context: ServiceWriteContext,
    service: Annotated[ServiceService, Depends(get_service_service)],
) -> ServiceResponse:
    result = service.deactivate(context, service_id)
    return ServiceResponse.model_validate(result)
