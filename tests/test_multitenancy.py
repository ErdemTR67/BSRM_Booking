from uuid import UUID

from fastapi import status
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.membership import Membership, MembershipRole
from app.models.user import User
from tests.support import (
    create_owned_tenant,
    create_user_headers as provision_user_headers,
)


PASSWORD = "correct-horse-battery-staple"


def create_user_headers(client: TestClient, email: str) -> dict[str, str]:
    return provision_user_headers(
        client, email, first_name="Tenant", last_name="User"
    )


def create_tenant(
    client: TestClient,
    headers: dict[str, str],
    *,
    name: str = "Tenant One",
    slug: str = "tenant-one",
) -> dict[str, object]:
    return create_owned_tenant(client, headers, name=name, slug=slug)


def add_membership(
    session: Session,
    *,
    tenant_id: str,
    email: str,
    role: MembershipRole,
) -> None:
    user = session.execute(select(User).where(User.email == email)).scalar_one()
    session.add(
        Membership(
            tenant_id=UUID(tenant_id),
            user_id=user.id,
            role=role.value,
            is_active=True,
        )
    )
    session.commit()


def location_payload(slug: str) -> dict[str, str]:
    return {
        "name": slug.replace("-", " ").title(),
        "slug": slug,
        "timezone": "Europe/Brussels",
        "country_code": "BE",
    }


def test_tenant_routes_require_authentication(client: TestClient) -> None:
    response = client.get("/api/v1/tenants")

    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert response.json()["error"]["code"] == "invalid_access_token"


def test_tenant_creation_assigns_owner_and_list_is_user_scoped(
    client: TestClient,
    session: Session,
) -> None:
    alice_headers = create_user_headers(client, "alice@example.com")
    alice_tenant = create_tenant(client, alice_headers)

    membership = session.execute(
        select(Membership).where(
            Membership.tenant_id == UUID(alice_tenant["id"]),
        )
    ).scalar_one()
    assert membership.role == MembershipRole.OWNER.value
    assert membership.is_active

    bob_headers = create_user_headers(client, "bob@example.com")
    bob_tenant = create_tenant(
        client,
        bob_headers,
        name="Tenant Two",
        slug="tenant-two",
    )

    alice_list = client.get("/api/v1/tenants", headers=alice_headers)
    assert alice_list.status_code == status.HTTP_200_OK
    assert [tenant["id"] for tenant in alice_list.json()] == [alice_tenant["id"]]

    hidden_tenant = client.get(
        f"/api/v1/tenants/{bob_tenant['id']}",
        headers=alice_headers,
    )
    assert hidden_tenant.status_code == status.HTTP_404_NOT_FOUND
    assert hidden_tenant.json()["error"]["code"] == "tenant_not_found"


def test_inactive_membership_hides_tenant(
    client: TestClient,
    session: Session,
) -> None:
    headers = create_user_headers(client, "inactive-member@example.com")
    tenant = create_tenant(client, headers)
    membership = session.execute(
        select(Membership).where(Membership.tenant_id == UUID(tenant["id"]))
    ).scalar_one()
    membership.is_active = False
    session.commit()

    response = client.get(
        f"/api/v1/tenants/{tenant['id']}",
        headers=headers,
    )

    assert response.status_code == status.HTTP_404_NOT_FOUND
    assert response.json()["error"]["code"] == "tenant_not_found"


def test_tenant_role_permissions(
    client: TestClient,
    session: Session,
) -> None:
    owner_headers = create_user_headers(client, "owner@example.com")
    tenant = create_tenant(client, owner_headers)

    admin_headers = create_user_headers(client, "admin@example.com")
    manager_headers = create_user_headers(client, "manager@example.com")
    staff_headers = create_user_headers(client, "staff@example.com")
    add_membership(
        session,
        tenant_id=tenant["id"],
        email="admin@example.com",
        role=MembershipRole.ADMIN,
    )
    add_membership(
        session,
        tenant_id=tenant["id"],
        email="manager@example.com",
        role=MembershipRole.MANAGER,
    )
    add_membership(
        session,
        tenant_id=tenant["id"],
        email="staff@example.com",
        role=MembershipRole.STAFF,
    )

    admin_update = client.patch(
        f"/api/v1/tenants/{tenant['id']}",
        headers=admin_headers,
        json={"name": "Updated by Admin"},
    )
    assert admin_update.status_code == status.HTTP_200_OK

    for headers in (manager_headers, staff_headers):
        denied = client.patch(
            f"/api/v1/tenants/{tenant['id']}",
            headers=headers,
            json={"name": "Forbidden Update"},
        )
        assert denied.status_code == status.HTTP_403_FORBIDDEN
        assert denied.json()["error"]["code"] == "insufficient_permissions"

    admin_delete = client.delete(
        f"/api/v1/tenants/{tenant['id']}",
        headers=admin_headers,
    )
    assert admin_delete.status_code == status.HTTP_403_FORBIDDEN

    owner_delete = client.delete(
        f"/api/v1/tenants/{tenant['id']}",
        headers=owner_headers,
    )
    assert owner_delete.status_code == status.HTTP_200_OK
    assert owner_delete.json()["is_active"] is False


def test_location_roles_and_cross_tenant_resource_isolation(
    client: TestClient,
    session: Session,
) -> None:
    owner_headers = create_user_headers(client, "location-owner@example.com")
    tenant = create_tenant(client, owner_headers)

    owner_location = client.post(
        f"/api/v1/tenants/{tenant['id']}/locations",
        headers=owner_headers,
        json=location_payload("owner-location"),
    )
    assert owner_location.status_code == status.HTTP_201_CREATED

    admin_headers = create_user_headers(client, "location-admin@example.com")
    manager_headers = create_user_headers(client, "location-manager@example.com")
    staff_headers = create_user_headers(client, "location-staff@example.com")

    for email, role in (
        ("location-admin@example.com", MembershipRole.ADMIN),
        ("location-manager@example.com", MembershipRole.MANAGER),
        ("location-staff@example.com", MembershipRole.STAFF),
    ):
        add_membership(
            session,
            tenant_id=tenant["id"],
            email=email,
            role=role,
        )

    for headers, slug in (
        (admin_headers, "admin-location"),
        (manager_headers, "manager-location"),
    ):
        allowed = client.post(
            f"/api/v1/tenants/{tenant['id']}/locations",
            headers=headers,
            json=location_payload(slug),
        )
        assert allowed.status_code == status.HTTP_201_CREATED

    denied = client.post(
        f"/api/v1/tenants/{tenant['id']}/locations",
        headers=staff_headers,
        json=location_payload("staff-location"),
    )
    assert denied.status_code == status.HTTP_403_FORBIDDEN
    assert denied.json()["error"]["code"] == "insufficient_permissions"

    staff_read = client.get(
        f"/api/v1/tenants/{tenant['id']}/locations",
        headers=staff_headers,
    )
    assert staff_read.status_code == status.HTTP_200_OK
    assert len(staff_read.json()) == 3

    other_headers = create_user_headers(client, "other-owner@example.com")
    other_tenant = create_tenant(
        client,
        other_headers,
        name="Other Tenant",
        slug="other-tenant",
    )
    hidden_location = client.get(
        f"/api/v1/tenants/{other_tenant['id']}/locations/"
        f"{owner_location.json()['id']}",
        headers=other_headers,
    )

    assert hidden_location.status_code == status.HTTP_404_NOT_FOUND
    assert hidden_location.json()["error"]["code"] == "location_not_found"


def test_location_slug_scope_and_inactive_listing(client: TestClient) -> None:
    first_headers = create_user_headers(client, "location-lifecycle@example.com")
    first_tenant = create_tenant(
        client,
        first_headers,
        name="Location Lifecycle",
        slug="location-lifecycle",
    )
    first_url = f"/api/v1/tenants/{first_tenant['id']}/locations"
    first = client.post(
        first_url,
        headers=first_headers,
        json=location_payload("shared-location"),
    )
    assert first.status_code == status.HTTP_201_CREATED

    duplicate = client.post(
        first_url,
        headers=first_headers,
        json=location_payload("shared-location"),
    )
    assert duplicate.status_code == status.HTTP_409_CONFLICT
    assert duplicate.json()["error"]["code"] == "location_slug_already_exists"

    second_headers = create_user_headers(client, "location-lifecycle-two@example.com")
    second_tenant = create_tenant(
        client,
        second_headers,
        name="Location Lifecycle Two",
        slug="location-lifecycle-two",
    )
    same_slug_other_tenant = client.post(
        f"/api/v1/tenants/{second_tenant['id']}/locations",
        headers=second_headers,
        json=location_payload("shared-location"),
    )
    assert same_slug_other_tenant.status_code == status.HTTP_201_CREATED

    deactivated = client.delete(
        f"{first_url}/{first.json()['id']}",
        headers=first_headers,
    )
    assert deactivated.status_code == status.HTTP_200_OK
    assert deactivated.json()["is_active"] is False
    assert client.get(first_url, headers=first_headers).json() == []
    including_inactive = client.get(
        f"{first_url}?include_inactive=true",
        headers=first_headers,
    )
    assert [item["id"] for item in including_inactive.json()] == [first.json()["id"]]
