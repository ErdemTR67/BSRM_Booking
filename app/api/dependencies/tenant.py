from collections.abc import Callable
from typing import Annotated
from uuid import UUID

from fastapi import Depends, Header
from sqlalchemy.orm import Session

from app.api.dependencies.auth import CurrentUser
from app.core.database import get_database_session, set_session_tenant
from app.core.exceptions import InsufficientPermissionsError
from app.core.tenant_context import TenantContext
from app.models.membership import Membership, MembershipRole
from app.services.membership import MembershipService


def get_current_membership(
    tenant_id: UUID,
    current_user: CurrentUser,
    session: Annotated[Session, Depends(get_database_session)],
) -> Membership:
    return MembershipService(session).get_current(
        tenant_id=tenant_id,
        user_id=current_user.id,
    )


CurrentMembership = Annotated[Membership, Depends(get_current_membership)]


def get_tenant_context(
    membership: CurrentMembership,
    session: Annotated[Session, Depends(get_database_session)],
) -> TenantContext:
    set_session_tenant(session, membership.tenant_id)
    return _build_tenant_context(membership)


def _build_tenant_context(membership: Membership) -> TenantContext:
    return TenantContext(
        tenant_id=membership.tenant_id,
        user_id=membership.user_id,
        membership_id=membership.id,
        role=MembershipRole(membership.role),
    )


CurrentTenantContext = Annotated[TenantContext, Depends(get_tenant_context)]


def get_tenant_context_from_header(
    x_tenant_id: Annotated[UUID, Header(alias="X-Tenant-ID")],
    current_user: CurrentUser,
    session: Annotated[Session, Depends(get_database_session)],
) -> TenantContext:
    membership = MembershipService(session).get_current(
        tenant_id=x_tenant_id,
        user_id=current_user.id,
    )
    set_session_tenant(session, membership.tenant_id)
    return _build_tenant_context(membership)


HeaderTenantContext = Annotated[
    TenantContext,
    Depends(get_tenant_context_from_header),
]


def require_roles(
    *allowed_roles: MembershipRole,
) -> Callable[[TenantContext], TenantContext]:
    allowed = frozenset(allowed_roles)

    if not allowed:
        raise ValueError("At least one membership role must be allowed.")

    def check_role(context: CurrentTenantContext) -> TenantContext:
        if context.role not in allowed:
            raise InsufficientPermissionsError()

        return context

    return check_role


def require_header_roles(
    *allowed_roles: MembershipRole,
) -> Callable[[TenantContext], TenantContext]:
    allowed = frozenset(allowed_roles)

    if not allowed:
        raise ValueError("At least one membership role must be allowed.")

    def check_role(context: HeaderTenantContext) -> TenantContext:
        if context.role not in allowed:
            raise InsufficientPermissionsError()

        return context

    return check_role
