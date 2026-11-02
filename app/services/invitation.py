import smtplib
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode
from uuid import UUID, uuid4

from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.database import set_session_tenant, set_session_user
from app.core.email import InvitationEmailSender
from app.core.exceptions import (
    InvalidInvitationError,
    InvitationAccountExistsError,
    InvitationAlreadyResolvedError,
    InvitationDeliveryError,
    InvitationNotFoundError,
    InvitationPersistenceError,
    TenantNotFoundError,
)
from app.core.security import hash_password
from app.core.tokens import generate_invitation_token, hash_invitation_token
from app.models.membership import Membership
from app.models.tenant_invitation import TenantInvitation
from app.models.user import User
from app.repositories.tenant import TenantRepository
from app.repositories.tenant_invitation import TenantInvitationRepository
from app.repositories.user import UserRepository
from app.schemas.platform import InvitationAcceptRequest, InvitationStatus, TenantInvitationCreate


@dataclass(frozen=True)
class IssuedInvitation:
    invitation: TenantInvitation
    acceptance_url: str | None


class InvitationService:
    def __init__(
        self,
        session: Session,
        *,
        settings: Settings | None = None,
        email_sender: InvitationEmailSender | None = None,
    ) -> None:
        self.session = session
        self.settings = settings or get_settings()
        self.email_sender = email_sender or InvitationEmailSender(self.settings)
        self.repository = TenantInvitationRepository(session)
        self.tenant_repository = TenantRepository(session)
        self.user_repository = UserRepository(session)

    def create(
        self,
        *,
        tenant_id: UUID,
        invited_by_user_id: UUID,
        payload: TenantInvitationCreate,
    ) -> IssuedInvitation:
        tenant = self.tenant_repository.get_by_id(tenant_id)
        if tenant is None or not tenant.is_active:
            raise TenantNotFoundError(tenant_id)

        normalized_email = str(payload.email).strip().lower()
        raw_token = generate_invitation_token()
        now = datetime.now(timezone.utc)
        invitation = TenantInvitation(
            tenant_id=tenant_id,
            email=normalized_email,
            role=payload.role.value,
            token_hash=hash_invitation_token(raw_token),
            expires_at=now + timedelta(hours=self.settings.invitation_expire_hours),
            invited_by_user_id=invited_by_user_id,
        )

        try:
            self.repository.revoke_pending_for_email(tenant_id, normalized_email)
            self.repository.add(invitation)
            self.session.commit()
        except IntegrityError as error:
            self.session.rollback()
            raise InvitationPersistenceError() from error

        self.session.refresh(invitation)
        invitation_url = self._build_invitation_url(raw_token)

        if self.settings.email_delivery_mode == "smtp":
            try:
                self.email_sender.send(
                    recipient=normalized_email,
                    tenant_name=tenant.name,
                    invitation_url=invitation_url,
                )
                invitation.sent_at = datetime.now(timezone.utc)
                self.session.commit()
                self.session.refresh(invitation)
            except (OSError, smtplib.SMTPException) as error:
                self.session.rollback()
                raise InvitationDeliveryError() from error

        return IssuedInvitation(
            invitation=invitation,
            acceptance_url=(
                invitation_url if self.settings.app_environment != "production" else None
            ),
        )

    def list_by_tenant(self, tenant_id: UUID) -> list[TenantInvitation]:
        tenant = self.tenant_repository.get_by_id(tenant_id)
        if tenant is None:
            raise TenantNotFoundError(tenant_id)
        return self.repository.list_by_tenant(tenant_id)

    def revoke(self, invitation_id: UUID) -> TenantInvitation:
        invitation = self.repository.get_by_id(invitation_id)
        if invitation is None:
            raise InvitationNotFoundError(invitation_id)
        if invitation.accepted_at is not None or invitation.revoked_at is not None:
            raise InvitationAlreadyResolvedError()

        invitation.revoked_at = datetime.now(timezone.utc)
        try:
            self.session.commit()
        except IntegrityError as error:
            self.session.rollback()
            raise InvitationPersistenceError() from error
        self.session.refresh(invitation)
        return invitation

    def get_for_acceptance(self, raw_token: str) -> TenantInvitation:
        invitation = self.repository.get_for_acceptance(
            hash_invitation_token(raw_token)
        )
        if invitation is None:
            raise InvalidInvitationError()
        return invitation

    def accept_new_user(self, payload: InvitationAcceptRequest) -> User:
        token_hash = hash_invitation_token(payload.token)
        invitation = self.repository.get_for_acceptance(token_hash)
        if invitation is None:
            raise InvalidInvitationError()

        if self.user_repository.get_by_email(invitation.email) is not None:
            raise InvitationAccountExistsError()

        user = User(
            email=invitation.email,
            password_hash=hash_password(payload.password),
            first_name=payload.first_name.strip(),
            last_name=payload.last_name.strip(),
            is_active=True,
        )

        try:
            self.user_repository.add(user)
            membership = self.repository.accept(
                token_hash=token_hash,
                user_id=user.id,
                membership_id=uuid4(),
            )
            if membership is None:
                raise InvalidInvitationError()
            set_session_user(self.session, user.id)
            set_session_tenant(self.session, membership.tenant_id)
            self.session.commit()
        except InvalidInvitationError:
            self.session.rollback()
            raise
        except (DBAPIError, IntegrityError) as error:
            self.session.rollback()
            raise InvalidInvitationError() from error

        self.session.refresh(user)
        return user

    def accept_existing_user(self, raw_token: str, user: User) -> Membership:
        token_hash = hash_invitation_token(raw_token)
        invitation = self.repository.get_for_acceptance(token_hash)
        if invitation is None or invitation.email.lower() != user.email.lower():
            raise InvalidInvitationError()

        try:
            membership = self.repository.accept(
                token_hash=token_hash,
                user_id=user.id,
                membership_id=uuid4(),
            )
            if membership is None:
                raise InvalidInvitationError()
            set_session_user(self.session, user.id)
            set_session_tenant(self.session, membership.tenant_id)
            self.session.commit()
        except InvalidInvitationError:
            self.session.rollback()
            raise
        except (DBAPIError, IntegrityError) as error:
            self.session.rollback()
            raise InvalidInvitationError() from error

        self.session.refresh(membership)
        return membership

    @staticmethod
    def status(invitation: TenantInvitation) -> InvitationStatus:
        if invitation.accepted_at is not None:
            return InvitationStatus.ACCEPTED
        if invitation.revoked_at is not None:
            return InvitationStatus.REVOKED
        if invitation.expires_at <= datetime.now(timezone.utc):
            return InvitationStatus.EXPIRED
        return InvitationStatus.PENDING

    def _build_invitation_url(self, raw_token: str) -> str:
        separator = "&" if "?" in self.settings.invitation_frontend_url else "?"
        return (
            f"{self.settings.invitation_frontend_url}{separator}"
            f"{urlencode({'token': raw_token})}"
        )
