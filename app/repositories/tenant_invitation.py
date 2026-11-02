from uuid import UUID

from sqlalchemy import select, text, update
from sqlalchemy.orm import Session

from app.models.membership import Membership
from app.models.tenant_invitation import TenantInvitation


class TenantInvitationRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get_by_id(self, invitation_id: UUID) -> TenantInvitation | None:
        return self.session.scalar(
            select(TenantInvitation).where(TenantInvitation.id == invitation_id)
        )

    def list_by_tenant(self, tenant_id: UUID) -> list[TenantInvitation]:
        statement = (
            select(TenantInvitation)
            .where(TenantInvitation.tenant_id == tenant_id)
            .order_by(TenantInvitation.created_at.desc())
        )
        return list(self.session.scalars(statement))

    def revoke_pending_for_email(self, tenant_id: UUID, email: str) -> None:
        self.session.execute(
            update(TenantInvitation)
            .where(
                TenantInvitation.tenant_id == tenant_id,
                TenantInvitation.email == email,
                TenantInvitation.accepted_at.is_(None),
                TenantInvitation.revoked_at.is_(None),
            )
            .values(revoked_at=text("CURRENT_TIMESTAMP"))
        )

    def add(self, invitation: TenantInvitation) -> TenantInvitation:
        self.session.add(invitation)
        self.session.flush()
        return invitation

    def get_for_acceptance(self, token_hash: str) -> TenantInvitation | None:
        statement = select(TenantInvitation).from_statement(
            text("SELECT * FROM app_get_invitation_for_acceptance(:token_hash)")
        )
        return self.session.scalar(statement.params(token_hash=token_hash))

    def accept(
        self,
        *,
        token_hash: str,
        user_id: UUID,
        membership_id: UUID,
    ) -> Membership | None:
        statement = select(Membership).from_statement(
            text(
                "SELECT * FROM app_accept_tenant_invitation("
                ":token_hash, :user_id, :membership_id)"
            )
        )
        return self.session.scalar(
            statement.params(
                token_hash=token_hash,
                user_id=user_id,
                membership_id=membership_id,
            )
        )
