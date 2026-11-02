import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from uuid import UUID

import jwt
from jwt import InvalidTokenError

from app.core.config import Settings, get_settings


class AccessTokenError(Exception):
    """Raised when an access token is invalid or expired."""


def generate_refresh_token() -> str:
    return secrets.token_urlsafe(64)


def hash_refresh_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def generate_invitation_token() -> str:
    return secrets.token_urlsafe(48)


def hash_invitation_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def generate_booking_site_key(*, production: bool) -> str:
    prefix = "bsrm_pk_live_" if production else "bsrm_pk_test_"
    return prefix + secrets.token_urlsafe(32)


def hash_booking_site_key(key: str) -> str:
    return hashlib.sha256(key.encode("utf-8")).hexdigest()


def create_access_token(
    user_id: UUID,
    *,
    settings: Settings | None = None,
    now: datetime | None = None,
) -> tuple[str, int]:
    active_settings = settings or get_settings()
    issued_at = now or datetime.now(timezone.utc)
    expires_in = active_settings.access_token_expire_minutes * 60
    expires_at = issued_at + timedelta(seconds=expires_in)

    payload = {
        "sub": str(user_id),
        "type": "access",
        "iat": issued_at,
        "exp": expires_at,
        "iss": active_settings.jwt_issuer,
        "aud": active_settings.jwt_audience,
    }
    token = jwt.encode(
        payload,
        active_settings.jwt_secret_key.get_secret_value(),
        algorithm=active_settings.jwt_algorithm,
    )

    return token, expires_in


def decode_access_token(
    token: str,
    *,
    settings: Settings | None = None,
) -> UUID:
    active_settings = settings or get_settings()

    try:
        payload = jwt.decode(
            token,
            active_settings.jwt_secret_key.get_secret_value(),
            algorithms=[active_settings.jwt_algorithm],
            audience=active_settings.jwt_audience,
            issuer=active_settings.jwt_issuer,
            options={"require": ["sub", "type", "iat", "exp", "iss", "aud"]},
        )

        if payload.get("type") != "access":
            raise AccessTokenError("Unexpected token type.")

        return UUID(payload["sub"])
    except (InvalidTokenError, KeyError, TypeError, ValueError) as error:
        raise AccessTokenError("Invalid or expired access token.") from error
