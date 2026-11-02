from uuid import UUID

from sqlalchemy.orm import Session

from app.core.exceptions import TenantNotFoundError
from app.models.membership import Membership
from app.repositories.membership import MembershipRepository


class MembershipService:
    def __init__(self, session: Session) -> None:
        self.repository = MembershipRepository(session)

    def get_current(self, tenant_id: UUID, user_id: UUID) -> Membership:
        membership = self.repository.get_active_by_tenant_and_user(
            tenant_id=tenant_id,
            user_id=user_id,
        )

        if membership is None:
            raise TenantNotFoundError(tenant_id)

        return membership

    def list_active_for_user(self, user_id: UUID) -> list[Membership]:
        return self.repository.list_active_by_user(user_id)
