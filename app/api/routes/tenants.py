from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.dependencies.auth import CurrentUser
from app.api.dependencies.tenant import CurrentTenantContext, require_roles
from app.core.database import get_database_session
from app.core.tenant_context import TenantContext
from app.models.membership import MembershipRole
from app.schemas.tenant import TenantResponse, TenantUpdate
from app.services.tenant import TenantService


router = APIRouter(prefix="/tenants", tags=["Tenants"])


def get_tenant_service(
    session: Annotated[Session, Depends(get_database_session)],
) -> TenantService:
    return TenantService(session)


TenantAdminContext = Annotated[
    TenantContext,
    Depends(require_roles(MembershipRole.OWNER, MembershipRole.ADMIN)),
]
TenantOwnerContext = Annotated[
    TenantContext,
    Depends(require_roles(MembershipRole.OWNER)),
]


@router.get("", response_model=list[TenantResponse])
def list_tenants(
    current_user: CurrentUser,
    service: Annotated[TenantService, Depends(get_tenant_service)],
) -> list[TenantResponse]:
    tenants = service.list_for_user(current_user.id)
    return [TenantResponse.model_validate(tenant) for tenant in tenants]


@router.get("/{tenant_id}", response_model=TenantResponse)
def get_tenant(
    context: CurrentTenantContext,
    service: Annotated[TenantService, Depends(get_tenant_service)],
) -> TenantResponse:
    tenant = service.get_by_id(context.tenant_id)
    return TenantResponse.model_validate(tenant)


@router.patch("/{tenant_id}", response_model=TenantResponse)
def update_tenant(
    payload: TenantUpdate,
    context: TenantAdminContext,
    service: Annotated[TenantService, Depends(get_tenant_service)],
) -> TenantResponse:
    tenant = service.update(context.tenant_id, payload)
    return TenantResponse.model_validate(tenant)


@router.delete("/{tenant_id}", response_model=TenantResponse)
def deactivate_tenant(
    context: TenantOwnerContext,
    service: Annotated[TenantService, Depends(get_tenant_service)],
) -> TenantResponse:
    tenant = service.deactivate(context.tenant_id)
    return TenantResponse.model_validate(tenant)
