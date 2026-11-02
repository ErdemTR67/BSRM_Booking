from uuid import UUID, uuid4

from fastapi import status
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.core.tokens import decode_access_token
from app.models.membership import Membership, MembershipRole
from app.models.tenant import Tenant
from app.models.user import User
from app.schemas.tenant import TenantResponse


PASSWORD = "correct-horse-battery-staple"


def get_test_session(client: TestClient) -> Session:
    return client.app.state.test_session


def create_user_headers(
    client: TestClient,
    email: str,
    *,
    first_name: str = "Test",
    last_name: str = "User",
    password: str = PASSWORD,
) -> dict[str, str]:
    session = get_test_session(client)
    normalized_email = email.strip().lower()
    user = User(
        email=normalized_email,
        password_hash=hash_password(password),
        first_name=first_name,
        last_name=last_name,
        is_active=True,
    )
    session.add(user)
    session.commit()

    login = client.post(
        "/api/v1/auth/login",
        data={"username": normalized_email, "password": password},
    )
    assert login.status_code == status.HTTP_200_OK
    return {"Authorization": f"Bearer {login.json()['access_token']}"}


def create_owned_tenant(
    client: TestClient,
    headers: dict[str, str],
    *,
    name: str,
    slug: str,
) -> dict[str, object]:
    session = get_test_session(client)
    token = headers["Authorization"].removeprefix("Bearer ")
    user_id = decode_access_token(token)
    tenant = Tenant(id=uuid4(), name=name, slug=slug, is_active=True)
    session.add(tenant)
    session.flush()
    session.add(
        Membership(
            tenant_id=tenant.id,
            user_id=user_id,
            role=MembershipRole.OWNER.value,
            is_active=True,
        )
    )
    session.commit()
    session.refresh(tenant)
    return TenantResponse.model_validate(tenant).model_dump(mode="json")


def add_membership(
    client: TestClient,
    *,
    tenant_id: str,
    email: str,
    role: MembershipRole,
) -> User:
    session = get_test_session(client)
    user = session.query(User).filter(User.email == email.strip().lower()).one()
    session.add(
        Membership(
            tenant_id=UUID(tenant_id),
            user_id=user.id,
            role=role.value,
            is_active=True,
        )
    )
    session.commit()
    return user
