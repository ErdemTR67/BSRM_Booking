from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.api.dependencies.platform import CurrentPlatformAdmin
from app.core.database import get_database_session
from app.models.tenant_invitation import TenantInvitation
from app.schemas.platform import (
    TenantInvitationCreate,
    TenantInvitationResponse,
)
from app.schemas.tenant import TenantCreate, TenantResponse, TenantUpdate
from app.services.invitation import InvitationService, IssuedInvitation
from app.services.tenant import TenantService


router = APIRouter(prefix="/platform", tags=["Platform administration"])


def get_tenant_service(
    session: Annotated[Session, Depends(get_database_session)],
) -> TenantService:
    return TenantService(session)


def get_invitation_service(
    session: Annotated[Session, Depends(get_database_session)],
) -> InvitationService:
    return InvitationService(session)


def _invitation_response(
    service: InvitationService,
    invitation: TenantInvitation,
    *,
    acceptance_url: str | None = None,
) -> TenantInvitationResponse:
    return TenantInvitationResponse(
        id=invitation.id,
        tenant_id=invitation.tenant_id,
        email=invitation.email,
        role=invitation.role,
        status=service.status(invitation),
        expires_at=invitation.expires_at,
        accepted_at=invitation.accepted_at,
        revoked_at=invitation.revoked_at,
        sent_at=invitation.sent_at,
        created_at=invitation.created_at,
        acceptance_url=acceptance_url,
    )


@router.post(
    "/tenants",
    response_model=TenantResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_tenant(
    payload: TenantCreate,
    platform_admin: CurrentPlatformAdmin,
    service: Annotated[TenantService, Depends(get_tenant_service)],
) -> TenantResponse:
    del platform_admin
    return TenantResponse.model_validate(service.create(payload))


@router.get("/tenants", response_model=list[TenantResponse])
def list_tenants(
    platform_admin: CurrentPlatformAdmin,
    service: Annotated[TenantService, Depends(get_tenant_service)],
) -> list[TenantResponse]:
    del platform_admin
    return [TenantResponse.model_validate(tenant) for tenant in service.list_all()]


@router.get("/tenants/{tenant_id}", response_model=TenantResponse)
def get_tenant(
    tenant_id: UUID,
    platform_admin: CurrentPlatformAdmin,
    service: Annotated[TenantService, Depends(get_tenant_service)],
) -> TenantResponse:
    del platform_admin
    return TenantResponse.model_validate(service.get_by_id(tenant_id))


@router.patch("/tenants/{tenant_id}", response_model=TenantResponse)
def update_tenant(
    tenant_id: UUID,
    payload: TenantUpdate,
    platform_admin: CurrentPlatformAdmin,
    service: Annotated[TenantService, Depends(get_tenant_service)],
) -> TenantResponse:
    del platform_admin
    return TenantResponse.model_validate(service.update(tenant_id, payload))


@router.delete("/tenants/{tenant_id}", response_model=TenantResponse)
def deactivate_tenant(
    tenant_id: UUID,
    platform_admin: CurrentPlatformAdmin,
    service: Annotated[TenantService, Depends(get_tenant_service)],
) -> TenantResponse:
    del platform_admin
    return TenantResponse.model_validate(service.deactivate(tenant_id))


@router.post(
    "/tenants/{tenant_id}/invitations",
    response_model=TenantInvitationResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_invitation(
    tenant_id: UUID,
    payload: TenantInvitationCreate,
    platform_admin: CurrentPlatformAdmin,
    service: Annotated[InvitationService, Depends(get_invitation_service)],
) -> TenantInvitationResponse:
    issued: IssuedInvitation = service.create(
        tenant_id=tenant_id,
        invited_by_user_id=platform_admin.user_id,
        payload=payload,
    )
    return _invitation_response(
        service,
        issued.invitation,
        acceptance_url=issued.acceptance_url,
    )


@router.get(
    "/tenants/{tenant_id}/invitations",
    response_model=list[TenantInvitationResponse],
)
def list_invitations(
    tenant_id: UUID,
    platform_admin: CurrentPlatformAdmin,
    service: Annotated[InvitationService, Depends(get_invitation_service)],
) -> list[TenantInvitationResponse]:
    del platform_admin
    return [
        _invitation_response(service, invitation)
        for invitation in service.list_by_tenant(tenant_id)
    ]


@router.post(
    "/invitations/{invitation_id}/revoke",
    response_model=TenantInvitationResponse,
)
def revoke_invitation(
    invitation_id: UUID,
    platform_admin: CurrentPlatformAdmin,
    service: Annotated[InvitationService, Depends(get_invitation_service)],
) -> TenantInvitationResponse:
    del platform_admin
    return _invitation_response(service, service.revoke(invitation_id))
