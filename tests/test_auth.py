from datetime import datetime, timedelta, timezone

from fastapi import status
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.tokens import create_access_token, decode_access_token, hash_refresh_token
from app.core.security import hash_password
from app.models.refresh_token import RefreshToken
from app.models.user import User
from app.schemas.user import UserResponse
from tests.support import get_test_session


PASSWORD = "correct-horse-battery-staple"


def register_user(
    client: TestClient,
    *,
    email: str = "auth@example.com",
) -> dict[str, object]:
    session = get_test_session(client)
    user = User(
        email=email.strip().lower(),
        password_hash=hash_password(PASSWORD),
        first_name="Auth",
        last_name="User",
        is_active=True,
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    return UserResponse.model_validate(user).model_dump(mode="json")


def login_user(
    client: TestClient,
    *,
    email: str = "auth@example.com",
    password: str = PASSWORD,
) -> dict[str, object]:
    response = client.post(
        "/api/v1/auth/login",
        data={"username": email, "password": password},
    )
    assert response.status_code == status.HTTP_200_OK
    return response.json()


def test_public_register_is_not_exposed(client: TestClient) -> None:
    response = client.post(
        "/api/v1/auth/register",
        json={
            "email": "OWNER@example.com",
            "password": PASSWORD,
            "first_name": "Other",
            "last_name": "User",
        },
    )
    assert response.status_code == status.HTTP_404_NOT_FOUND


def test_login_issues_access_and_hashed_refresh_tokens(
    client: TestClient,
    session: Session,
) -> None:
    user = register_user(client)
    tokens = login_user(client)

    assert tokens["token_type"] == "bearer"
    assert str(decode_access_token(tokens["access_token"])) == user["id"]

    stored_token = session.execute(select(RefreshToken)).scalar_one()
    assert stored_token.token_hash == hash_refresh_token(tokens["refresh_token"])
    assert stored_token.token_hash != tokens["refresh_token"]


def test_login_rejects_bad_password(client: TestClient) -> None:
    register_user(client)

    response = client.post(
        "/api/v1/auth/login",
        data={"username": "auth@example.com", "password": "wrong-password"},
    )

    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert response.json()["error"]["code"] == "invalid_credentials"


def test_login_rejects_inactive_user(
    client: TestClient,
    session: Session,
) -> None:
    register_user(client)
    user = session.execute(
        select(User).where(User.email == "auth@example.com")
    ).scalar_one()
    user.is_active = False
    session.commit()

    response = client.post(
        "/api/v1/auth/login",
        data={"username": "auth@example.com", "password": PASSWORD},
    )

    assert response.status_code == status.HTTP_403_FORBIDDEN
    assert response.json()["error"]["code"] == "inactive_user"


def test_me_returns_authenticated_user(client: TestClient) -> None:
    user = register_user(client)
    tokens = login_user(client)

    response = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {tokens['access_token']}"},
    )

    assert response.status_code == status.HTTP_200_OK
    assert response.json()["id"] == user["id"]


def test_me_rejects_invalid_access_token(client: TestClient) -> None:
    response = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": "Bearer invalid-token"},
    )

    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert response.json()["error"]["code"] == "invalid_access_token"


def test_refresh_rotates_token_and_rejects_reuse(client: TestClient) -> None:
    register_user(client)
    original_tokens = login_user(client)

    rotated = client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": original_tokens["refresh_token"]},
    )

    assert rotated.status_code == status.HTTP_200_OK
    rotated_tokens = rotated.json()
    assert rotated_tokens["refresh_token"] != original_tokens["refresh_token"]

    reused = client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": original_tokens["refresh_token"]},
    )
    assert reused.status_code == status.HTTP_401_UNAUTHORIZED
    assert reused.json()["error"]["code"] == "invalid_refresh_token"

    current = client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": rotated_tokens["refresh_token"]},
    )
    assert current.status_code == status.HTTP_200_OK


def test_logout_revokes_refresh_token(client: TestClient) -> None:
    register_user(client)
    tokens = login_user(client)

    logout = client.post(
        "/api/v1/auth/logout",
        json={"refresh_token": tokens["refresh_token"]},
    )
    assert logout.status_code == status.HTTP_204_NO_CONTENT
    assert logout.content == b""

    refresh = client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": tokens["refresh_token"]},
    )
    assert refresh.status_code == status.HTTP_401_UNAUTHORIZED
    assert refresh.json()["error"]["code"] == "invalid_refresh_token"


def test_expired_access_token_is_rejected(client: TestClient, session: Session) -> None:
    register_user(client, email="expired-access@example.com")
    user = session.execute(
        select(User).where(User.email == "expired-access@example.com")
    ).scalar_one()
    expired_token, _ = create_access_token(
        user.id,
        now=datetime.now(timezone.utc) - timedelta(hours=2),
    )

    response = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {expired_token}"},
    )

    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert response.json()["error"]["code"] == "invalid_access_token"


def test_expired_refresh_token_is_rejected(
    client: TestClient,
    session: Session,
) -> None:
    register_user(client, email="expired-refresh@example.com")
    tokens = login_user(client, email="expired-refresh@example.com")
    stored_token = session.execute(select(RefreshToken)).scalar_one()
    stored_token.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
    session.commit()

    response = client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": tokens["refresh_token"]},
    )

    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert response.json()["error"]["code"] == "invalid_refresh_token"


def test_refresh_token_is_rejected_after_user_deactivation(
    client: TestClient,
    session: Session,
) -> None:
    register_user(client, email="inactive-refresh@example.com")
    tokens = login_user(client, email="inactive-refresh@example.com")
    user = session.execute(
        select(User).where(User.email == "inactive-refresh@example.com")
    ).scalar_one()
    user.is_active = False
    session.commit()

    response = client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": tokens["refresh_token"]},
    )

    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert response.json()["error"]["code"] == "invalid_refresh_token"
