from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.exceptions import (
    InactiveUserError,
    InvalidCredentialsError,
    InvalidRefreshTokenError,
    RefreshTokenPersistenceError,
)
from app.core.security import hash_password, verify_password
from app.core.tokens import (
    create_access_token,
    generate_refresh_token,
    hash_refresh_token,
)
from app.models.refresh_token import RefreshToken
from app.models.user import User
from app.repositories.refresh_token import RefreshTokenRepository
from app.repositories.user import UserRepository


_DUMMY_PASSWORD_HASH = hash_password("dummy-password-for-timing-protection")


@dataclass(frozen=True)
class AuthTokens:
    access_token: str
    refresh_token: str
    expires_in: int
    refresh_expires_in: int


class AuthService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.user_repository = UserRepository(session)
        self.refresh_token_repository = RefreshTokenRepository(session)

    def login(self, email: str, password: str) -> AuthTokens:
        normalized_email = email.strip().lower()
        user = self.user_repository.get_by_email(email=normalized_email)
        password_is_valid = verify_password(
            password=password,
            password_hash=(
                user.password_hash if user is not None else _DUMMY_PASSWORD_HASH
            ),
        )

        if user is None or not password_is_valid:
            raise InvalidCredentialsError()

        if not user.is_active:
            raise InactiveUserError(user.id)

        return self._issue_tokens(user)

    def refresh(self, raw_refresh_token: str) -> AuthTokens:
        now = datetime.now(timezone.utc)
        refresh_token = self.refresh_token_repository.get_by_hash(
            hash_refresh_token(raw_refresh_token),
            for_update=True,
        )

        if not self._is_usable(refresh_token, now):
            raise InvalidRefreshTokenError()

        user = self.user_repository.get_by_id(refresh_token.user_id)

        if user is None or not user.is_active:
            raise InvalidRefreshTokenError()

        return self._issue_tokens(user, replaced_token=refresh_token, now=now)

    def logout(self, raw_refresh_token: str) -> None:
        now = datetime.now(timezone.utc)
        refresh_token = self.refresh_token_repository.get_by_hash(
            hash_refresh_token(raw_refresh_token),
            for_update=True,
        )

        if not self._is_usable(refresh_token, now):
            raise InvalidRefreshTokenError()

        refresh_token.revoked_at = now
        self.session.commit()

    def _issue_tokens(
        self,
        user: User,
        *,
        replaced_token: RefreshToken | None = None,
        now: datetime | None = None,
    ) -> AuthTokens:
        issued_at = now or datetime.now(timezone.utc)
        settings = get_settings()
        refresh_expires_in = settings.refresh_token_expire_days * 24 * 60 * 60
        raw_refresh_token = generate_refresh_token()
        refresh_token = RefreshToken(
            user_id=user.id,
            token_hash=hash_refresh_token(raw_refresh_token),
            expires_at=issued_at + timedelta(seconds=refresh_expires_in),
        )

        try:
            self.refresh_token_repository.add(refresh_token)

            if replaced_token is not None:
                replaced_token.revoked_at = issued_at
                replaced_token.replaced_by_id = refresh_token.id

            access_token, expires_in = create_access_token(
                user.id,
                settings=settings,
                now=issued_at,
            )
            self.session.commit()
        except IntegrityError as error:
            self.session.rollback()
            raise RefreshTokenPersistenceError() from error

        return AuthTokens(
            access_token=access_token,
            refresh_token=raw_refresh_token,
            expires_in=expires_in,
            refresh_expires_in=refresh_expires_in,
        )

    @staticmethod
    def _is_usable(
        refresh_token: RefreshToken | None,
        now: datetime,
    ) -> bool:
        return (
            refresh_token is not None
            and refresh_token.revoked_at is None
            and refresh_token.expires_at > now
        )
