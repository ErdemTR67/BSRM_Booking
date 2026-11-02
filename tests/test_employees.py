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
        client, email, first_name="Employee", last_name="Tester"
    )


def create_tenant(
    client: TestClient,
    auth_headers: dict[str, str],
    *,
    name: str = "Employee Tenant",
    slug: str = "employee-tenant",
) -> dict[str, object]:
    return create_owned_tenant(client, auth_headers, name=name, slug=slug)


def tenant_headers(
    auth_headers: dict[str, str],
    tenant_id: str,
) -> dict[str, str]:
    return {**auth_headers, "X-Tenant-ID": tenant_id}


def create_location(
    client: TestClient,
    auth_headers: dict[str, str],
    tenant_id: str,
    *,
    slug: str = "main-location",
) -> dict[str, object]:
    response = client.post(
        f"/api/v1/tenants/{tenant_id}/locations",
        headers=auth_headers,
        json={
            "name": slug.replace("-", " ").title(),
            "slug": slug,
            "timezone": "Europe/Brussels",
            "country_code": "BE",
        },
    )
    assert response.status_code == status.HTTP_201_CREATED
    return response.json()


def create_employee(
    client: TestClient,
    headers: dict[str, str],
    location_id: str,
    *,
    first_name: str = "Ada",
    last_name: str = "Lovelace",
    is_bookable: bool = True,
    user_id: str | None = None,
) -> dict[str, object]:
    payload: dict[str, object] = {
        "location_id": location_id,
        "first_name": first_name,
        "last_name": last_name,
        "email": f"{first_name.lower()}@example.com",
        "phone": "+32 2 000 00 00",
        "display_color": "#123456",
        "is_bookable": is_bookable,
    }

    if user_id is not None:
        payload["user_id"] = user_id

    response = client.post("/api/v1/employees", headers=headers, json=payload)
    assert response.status_code == status.HTTP_201_CREATED
    return response.json()


def add_membership(
    session: Session,
    *,
    tenant_id: str,
    email: str,
    role: MembershipRole,
) -> User:
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
    return user


def setup_owner(
    client: TestClient,
    *,
    email: str = "employee-owner@example.com",
    tenant_name: str = "Employee Tenant",
    tenant_slug: str = "employee-tenant",
    location_slug: str = "main-location",
) -> tuple[dict[str, str], dict[str, str], dict[str, object], dict[str, object]]:
    auth_headers = create_user_headers(client, email)
    tenant = create_tenant(
        client,
        auth_headers,
        name=tenant_name,
        slug=tenant_slug,
    )
    location = create_location(
        client,
        auth_headers,
        tenant["id"],
        slug=location_slug,
    )
    return (
        auth_headers,
        tenant_headers(auth_headers, tenant["id"]),
        tenant,
        location,
    )


def test_employee_routes_require_authentication_and_tenant_header(
    client: TestClient,
) -> None:
    auth_headers = create_user_headers(client, "header-check@example.com")

    unauthenticated = client.get(
        "/api/v1/employees",
        headers={"X-Tenant-ID": "00000000-0000-0000-0000-000000000001"},
    )
    assert unauthenticated.status_code == status.HTTP_401_UNAUTHORIZED

    missing_tenant = client.get("/api/v1/employees", headers=auth_headers)
    assert missing_tenant.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT


def test_employee_crud_and_soft_deactivation(client: TestClient) -> None:
    _, headers, _, location = setup_owner(client)
    employee = create_employee(client, headers, location["id"])

    assert "tenant_id" not in employee
    assert employee["is_active"] is True
    assert employee["is_bookable"] is True

    read = client.get(f"/api/v1/employees/{employee['id']}", headers=headers)
    assert read.status_code == status.HTTP_200_OK

    updated = client.patch(
        f"/api/v1/employees/{employee['id']}",
        headers=headers,
        json={"first_name": "Grace", "is_bookable": False},
    )
    assert updated.status_code == status.HTTP_200_OK
    assert updated.json()["first_name"] == "Grace"
    assert updated.json()["is_bookable"] is False

    deleted = client.delete(
        f"/api/v1/employees/{employee['id']}",
        headers=headers,
    )
    assert deleted.status_code == status.HTTP_200_OK
    assert deleted.json()["is_active"] is False

    active_list = client.get("/api/v1/employees", headers=headers)
    assert active_list.status_code == status.HTTP_200_OK
    assert active_list.json()["items"] == []

    inactive_list = client.get(
        "/api/v1/employees?is_active=false",
        headers=headers,
    )
    assert [item["id"] for item in inactive_list.json()["items"]] == [employee["id"]]


def test_employee_filters(client: TestClient) -> None:
    auth_headers, headers, tenant, first_location = setup_owner(client)
    second_location = create_location(
        client,
        auth_headers,
        tenant["id"],
        slug="second-location",
    )
    create_employee(
        client,
        headers,
        first_location["id"],
        first_name="Ada",
        is_bookable=True,
    )
    create_employee(
        client,
        headers,
        first_location["id"],
        first_name="Alan",
        is_bookable=False,
    )
    create_employee(
        client,
        headers,
        second_location["id"],
        first_name="Grace",
        is_bookable=True,
    )

    by_location = client.get(
        f"/api/v1/employees?location_id={first_location['id']}",
        headers=headers,
    )
    assert len(by_location.json()["items"]) == 2
    assert by_location.json()["total"] == 2

    second_page = client.get(
        "/api/v1/employees?page=2&page_size=1",
        headers=headers,
    )
    assert second_page.status_code == status.HTTP_200_OK
    assert second_page.json()["page"] == 2
    assert second_page.json()["page_size"] == 1
    assert second_page.json()["total"] == 3
    assert len(second_page.json()["items"]) == 1

    bookable = client.get(
        "/api/v1/employees?is_bookable=true",
        headers=headers,
    )
    assert {item["first_name"] for item in bookable.json()["items"]} == {"Ada", "Grace"}

    not_bookable = client.get(
        "/api/v1/employees?is_bookable=false",
        headers=headers,
    )
    assert [item["first_name"] for item in not_bookable.json()["items"]] == ["Alan"]


def test_employee_user_requires_active_membership(
    client: TestClient,
    session: Session,
) -> None:
    _, headers, tenant, location = setup_owner(client)
    create_user_headers(client, "linked-member@example.com")
    member = add_membership(
        session,
        tenant_id=tenant["id"],
        email="linked-member@example.com",
        role=MembershipRole.STAFF,
    )
    linked = create_employee(
        client,
        headers,
        location["id"],
        user_id=str(member.id),
    )
    assert linked["user_id"] == str(member.id)

    create_user_headers(client, "outsider@example.com")
    outsider = session.execute(
        select(User).where(User.email == "outsider@example.com")
    ).scalar_one()
    denied = client.post(
        "/api/v1/employees",
        headers=headers,
        json={
            "location_id": location["id"],
            "user_id": str(outsider.id),
            "first_name": "Outside",
            "last_name": "User",
        },
    )
    assert denied.status_code == status.HTTP_404_NOT_FOUND
    assert denied.json()["error"]["code"] == "user_not_found"

    membership = session.execute(
        select(Membership).where(
            Membership.tenant_id == UUID(tenant["id"]),
            Membership.user_id == member.id,
        )
    ).scalar_one()
    membership.is_active = False
    session.commit()
    inactive_denied = client.patch(
        f"/api/v1/employees/{linked['id']}",
        headers=headers,
        json={"user_id": str(member.id)},
    )
    assert inactive_denied.status_code == status.HTTP_404_NOT_FOUND

def test_employee_isolation_for_locations_filters_and_resources(
    client: TestClient,
) -> None:
    _, first_headers, _, first_location = setup_owner(client)
    first_employee = create_employee(client, first_headers, first_location["id"])
    _, second_headers, _, second_location = setup_owner(
        client,
        email="second-owner@example.com",
        tenant_name="Second Tenant",
        tenant_slug="second-tenant",
        location_slug="second-location",
    )
    second_employee = create_employee(
        client,
        second_headers,
        second_location["id"],
        first_name="Second",
    )

    foreign_location = client.post(
        "/api/v1/employees",
        headers=first_headers,
        json={
            "location_id": second_location["id"],
            "first_name": "Hidden",
            "last_name": "Location",
        },
    )
    assert foreign_location.status_code == status.HTTP_404_NOT_FOUND
    assert foreign_location.json()["error"]["code"] == "location_not_found"

    foreign_filter = client.get(
        f"/api/v1/employees?location_id={second_location['id']}",
        headers=first_headers,
    )
    assert foreign_filter.status_code == status.HTTP_404_NOT_FOUND

    hidden_employee = client.get(
        f"/api/v1/employees/{second_employee['id']}",
        headers=first_headers,
    )
    assert hidden_employee.status_code == status.HTTP_404_NOT_FOUND
    assert hidden_employee.json()["error"]["code"] == "employee_not_found"

    invalid_move = client.patch(
        f"/api/v1/employees/{first_employee['id']}",
        headers=first_headers,
        json={"location_id": second_location["id"]},
    )
    assert invalid_move.status_code == status.HTTP_404_NOT_FOUND


def test_employee_role_permissions(
    client: TestClient,
    session: Session,
) -> None:
    _, owner_headers, tenant, location = setup_owner(client)
    role_headers: dict[MembershipRole, dict[str, str]] = {}

    for role in (
        MembershipRole.ADMIN,
        MembershipRole.MANAGER,
        MembershipRole.STAFF,
    ):
        email = f"employee-{role.value}@example.com"
        auth_headers = create_user_headers(client, email)
        add_membership(
            session,
            tenant_id=tenant["id"],
            email=email,
            role=role,
        )
        role_headers[role] = tenant_headers(auth_headers, tenant["id"])

    for role in (MembershipRole.ADMIN, MembershipRole.MANAGER):
        allowed = client.post(
            "/api/v1/employees",
            headers=role_headers[role],
            json={
                "location_id": location["id"],
                "first_name": role.value.title(),
                "last_name": "Employee",
            },
        )
        assert allowed.status_code == status.HTTP_201_CREATED

    staff_create = client.post(
        "/api/v1/employees",
        headers=role_headers[MembershipRole.STAFF],
        json={
            "location_id": location["id"],
            "first_name": "Staff",
            "last_name": "Employee",
        },
    )
    assert staff_create.status_code == status.HTTP_403_FORBIDDEN
    assert staff_create.json()["error"]["code"] == "insufficient_permissions"

    staff_read = client.get(
        "/api/v1/employees",
        headers=role_headers[MembershipRole.STAFF],
    )
    assert staff_read.status_code == status.HTTP_200_OK
    assert len(staff_read.json()["items"]) == 2

    employee_id = staff_read.json()["items"][0]["id"]
    staff_update = client.patch(
        f"/api/v1/employees/{employee_id}",
        headers=role_headers[MembershipRole.STAFF],
        json={"first_name": "Forbidden"},
    )
    assert staff_update.status_code == status.HTTP_403_FORBIDDEN

    owner_delete = client.delete(
        f"/api/v1/employees/{employee_id}",
        headers=owner_headers,
    )
    assert owner_delete.status_code == status.HTTP_200_OK
