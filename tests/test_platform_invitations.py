from datetime import datetime, timedelta, timezone
from urllib.parse import parse_qs, urlparse

from fastapi import status
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.tokens import hash_invitation_token
from app.models.membership import Membership, MembershipRole
from app.models.platform_role import PlatformRole, PlatformRoleName
from app.models.tenant_invitation import TenantInvitation
from app.models.user import User
from tests.support import PASSWORD, create_user_headers


def _platform_headers(client: TestClient, session: Session) -> dict[str, str]:
    headers = create_user_headers(
        client,
        "platform-admin@example.com",
        first_name="Platform",
        last_name="Admin",
    )
    user = session.scalar(
        select(User).where(User.email == "platform-admin@example.com")
    )
    assert user is not None
    session.add(
        PlatformRole(
            user_id=user.id,
            role=PlatformRoleName.PLATFORM_ADMIN.value,
            is_active=True,
        )
    )
    session.commit()
    return headers


def _create_tenant(client: TestClient, headers: dict[str, str]) -> dict[str, object]:
    response = client.post(
        "/api/v1/platform/tenants",
        headers=headers,
        json={"name": "Provisioned Company", "slug": "provisioned-company"},
    )
    assert response.status_code == status.HTTP_201_CREATED, response.text
    return response.json()


def _invite(
    client: TestClient,
    headers: dict[str, str],
    tenant_id: str,
    *,
    email: str = "invited-owner@example.com",
    role: str = "owner",
) -> tuple[dict[str, object], str]:
    response = client.post(
        f"/api/v1/platform/tenants/{tenant_id}/invitations",
        headers=headers,
        json={"email": email, "role": role},
    )
    assert response.status_code == status.HTTP_201_CREATED, response.text
    invitation = response.json()
    assert invitation["status"] == "pending"
    assert invitation["acceptance_url"] is not None
    token = parse_qs(urlparse(invitation["acceptance_url"]).query)["token"][0]
    return invitation, token


def test_normal_user_cannot_provision_tenant(client: TestClient) -> None:
    headers = create_user_headers(client, "normal-user@example.com")
    platform_response = client.post(
        "/api/v1/platform/tenants",
        headers=headers,
        json={"name": "Forbidden", "slug": "forbidden"},
    )
    assert platform_response.status_code == status.HTTP_403_FORBIDDEN
    assert platform_response.json()["error"]["code"] == "insufficient_permissions"

    legacy_response = client.post(
        "/api/v1/tenants",
        headers=headers,
        json={"name": "Forbidden", "slug": "forbidden"},
    )
    assert legacy_response.status_code == status.HTTP_405_METHOD_NOT_ALLOWED


def test_invitation_creates_user_and_owner_membership_once(
    client: TestClient,
    session: Session,
) -> None:
    platform_headers = _platform_headers(client, session)
    tenant = _create_tenant(client, platform_headers)
    invitation_response, raw_token = _invite(
        client, platform_headers, tenant["id"]
    )

    stored = session.get(TenantInvitation, invitation_response["id"])
    assert stored is not None
    assert stored.token_hash == hash_invitation_token(raw_token)
    assert raw_token not in stored.token_hash

    accepted = client.post(
        "/api/v1/auth/invitations/accept",
        json={
            "token": raw_token,
            "password": PASSWORD,
            "first_name": "Invited",
            "last_name": "Owner",
        },
    )
    assert accepted.status_code == status.HTTP_201_CREATED, accepted.text
    assert accepted.json()["email"] == "invited-owner@example.com"

    user = session.scalar(
        select(User).where(User.email == "invited-owner@example.com")
    )
    assert user is not None
    membership = session.scalar(
        select(Membership).where(
            Membership.tenant_id == tenant["id"],
            Membership.user_id == user.id,
        )
    )
    assert membership is not None
    assert membership.role == MembershipRole.OWNER.value
    assert membership.is_active

    reused = client.post(
        "/api/v1/auth/invitations/accept",
        json={
            "token": raw_token,
            "password": PASSWORD,
            "first_name": "Again",
            "last_name": "Again",
        },
    )
    assert reused.status_code == status.HTTP_401_UNAUTHORIZED
    assert reused.json()["error"]["code"] == "invalid_invitation"

    login = client.post(
        "/api/v1/auth/login",
        data={"username": "invited-owner@example.com", "password": PASSWORD},
    )
    assert login.status_code == status.HTTP_200_OK
    tenant_list = client.get(
        "/api/v1/tenants",
        headers={"Authorization": f"Bearer {login.json()['access_token']}"},
    )
    assert [item["id"] for item in tenant_list.json()] == [tenant["id"]]


def test_revoked_and_expired_invitations_are_rejected(
    client: TestClient,
    session: Session,
) -> None:
    platform_headers = _platform_headers(client, session)
    tenant = _create_tenant(client, platform_headers)
    invitation, revoked_token = _invite(client, platform_headers, tenant["id"])
    revoked = client.post(
        f"/api/v1/platform/invitations/{invitation['id']}/revoke",
        headers=platform_headers,
    )
    assert revoked.status_code == status.HTTP_200_OK
    assert revoked.json()["status"] == "revoked"

    rejected = client.post(
        "/api/v1/auth/invitations/accept",
        json={
            "token": revoked_token,
            "password": PASSWORD,
            "first_name": "No",
            "last_name": "Access",
        },
    )
    assert rejected.status_code == status.HTTP_401_UNAUTHORIZED

    second, expired_token = _invite(
        client,
        platform_headers,
        tenant["id"],
        email="expired@example.com",
    )
    stored = session.get(TenantInvitation, second["id"])
    assert stored is not None
    stored.expires_at = datetime.now(timezone.utc) - timedelta(days=1)
    session.commit()
    expired = client.post(
        "/api/v1/auth/invitations/accept",
        json={
            "token": expired_token,
            "password": PASSWORD,
            "first_name": "No",
            "last_name": "Access",
        },
    )
    assert expired.status_code == status.HTTP_401_UNAUTHORIZED


def test_existing_user_must_sign_in_and_email_must_match(
    client: TestClient,
    session: Session,
) -> None:
    platform_headers = _platform_headers(client, session)
    tenant = _create_tenant(client, platform_headers)
    existing_headers = create_user_headers(client, "existing@example.com")
    other_headers = create_user_headers(client, "other-existing@example.com")
    _, token = _invite(
        client,
        platform_headers,
        tenant["id"],
        email="existing@example.com",
        role="staff",
    )

    public_accept = client.post(
        "/api/v1/auth/invitations/accept",
        json={
            "token": token,
            "password": PASSWORD,
            "first_name": "Existing",
            "last_name": "User",
        },
    )
    assert public_accept.status_code == status.HTTP_409_CONFLICT
    assert public_accept.json()["error"]["code"] == "invitation_account_exists"

    wrong_user = client.post(
        "/api/v1/auth/invitations/accept-existing",
        headers=other_headers,
        json={"token": token},
    )
    assert wrong_user.status_code == status.HTTP_401_UNAUTHORIZED

    accepted = client.post(
        "/api/v1/auth/invitations/accept-existing",
        headers=existing_headers,
        json={"token": token},
    )
    assert accepted.status_code == status.HTTP_200_OK
    assert accepted.json()["tenant_id"] == tenant["id"]
    assert accepted.json()["role"] == "staff"
