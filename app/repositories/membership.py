from uuid import UUID

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.models.membership import Membership


class MembershipRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get_active_by_tenant_and_user(
        self,
        tenant_id: UUID,
        user_id: UUID,
    ) -> Membership | None:
        statement = select(Membership).from_statement(
            text(
                "SELECT * FROM app_get_active_membership(:tenant_id, :user_id)"
            )
        )
        return self.session.scalar(
            statement.params(tenant_id=tenant_id, user_id=user_id)
        )

    def list_active_by_user(self, user_id: UUID) -> list[Membership]:
        statement = select(Membership).from_statement(
            text(
                "SELECT * FROM app_list_active_memberships(:user_id)"
            )
        )
        return list(self.session.scalars(statement.params(user_id=user_id)))

    def get_active_in_current_tenant(
        self,
        tenant_id: UUID,
        user_id: UUID,
    ) -> Membership | None:
        statement = select(Membership).where(
            Membership.tenant_id == tenant_id,
            Membership.user_id == user_id,
            Membership.is_active.is_(True),
        )
        return self.session.scalar(statement)

    def add(self, membership: Membership) -> Membership:
        self.session.add(membership)
        self.session.flush()
        return membership
