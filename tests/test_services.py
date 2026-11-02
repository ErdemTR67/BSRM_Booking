from uuid import UUID

import pytest
from fastapi import status
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.employee import Employee
from app.models.employee_service import EmployeeService
from app.models.location import Location
from app.models.membership import Membership, MembershipRole
from app.models.service import Service
from app.models.tenant import Tenant
from app.models.user import User
from tests.support import (
    create_owned_tenant,
    create_user_headers as provision_user_headers,
)


PASSWORD = "correct-horse-battery-staple"


def create_user_headers(client: TestClient, email: str) -> dict[str, str]:
    return provision_user_headers(
        client, email, first_name="Service", last_name="Tester"
    )


def tenant_headers(auth_headers: dict[str, str], tenant_id: str) -> dict[str, str]:
    return {**auth_headers, "X-Tenant-ID": tenant_id}


def setup_owner(
    client: TestClient,
    *,
    email: str = "service-owner@example.com",
    tenant_name: str = "Service Tenant",
    tenant_slug: str = "service-tenant",
    location_slug: str = "service-location",
) -> tuple[
    dict[str, str],
    dict[str, str],
    dict[str, object],
    dict[str, object],
    dict[str, object],
]:
    auth_headers = create_user_headers(client, email)
    tenant = create_owned_tenant(
        client, auth_headers, name=tenant_name, slug=tenant_slug
    )
    headers = tenant_headers(auth_headers, tenant["id"])
    location_response = client.post(
        f"/api/v1/tenants/{tenant['id']}/locations",
        headers=auth_headers,
        json={
            "name": location_slug.replace("-", " ").title(),
            "slug": location_slug,
            "timezone": "Europe/Brussels",
            "country_code": "BE",
        },
    )
    assert location_response.status_code == status.HTTP_201_CREATED
    location = location_response.json()
    employee_response = client.post(
        "/api/v1/employees",
        headers=headers,
        json={
            "location_id": location["id"],
            "first_name": "Ada",
            "last_name": "Lovelace",
        },
    )
    assert employee_response.status_code == status.HTTP_201_CREATED
    return auth_headers, headers, tenant, location, employee_response.json()


def create_service(
    client: TestClient,
    headers: dict[str, str],
    *,
    location_id: str | None = None,
    name: str = "Consultation",
) -> dict[str, object]:
    response = client.post(
        "/api/v1/services",
        headers=headers,
        json={
            "location_id": location_id,
            "name": name,
            "description": "A bookable service",
            "duration_minutes": 30,
            "buffer_before_minutes": 5,
            "buffer_after_minutes": 10,
            "price_cents": 5000,
            "currency": "eur",
        },
    )
    assert response.status_code == status.HTTP_201_CREATED
    return response.json()


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


def test_service_crud_and_soft_deactivation(client: TestClient) -> None:
    _, headers, _, location, _ = setup_owner(client)
    service = create_service(client, headers, location_id=location["id"])

    assert "tenant_id" not in service
    assert service["currency"] == "EUR"
    assert service["is_active"] is True

    read = client.get(f"/api/v1/services/{service['id']}", headers=headers)
    assert read.status_code == status.HTTP_200_OK

    updated = client.patch(
        f"/api/v1/services/{service['id']}",
        headers=headers,
        json={
            "duration_minutes": 45,
            "buffer_before_minutes": 0,
            "price_cents": None,
            "currency": "usd",
        },
    )
    assert updated.status_code == status.HTTP_200_OK
    assert updated.json()["duration_minutes"] == 45
    assert updated.json()["price_cents"] is None
    assert updated.json()["currency"] == "USD"

    deleted = client.delete(f"/api/v1/services/{service['id']}", headers=headers)
    assert deleted.status_code == status.HTTP_200_OK
    assert deleted.json()["is_active"] is False

    active = client.get("/api/v1/services", headers=headers)
    assert active.json()["items"] == []
    assert active.json()["total"] == 0
    inactive = client.get("/api/v1/services?is_active=false", headers=headers)
    assert [item["id"] for item in inactive.json()["items"]] == [service["id"]]
    assert inactive.json()["total"] == 1


@pytest.mark.parametrize(
    "invalid_fields",
    [
        {"duration_minutes": 0},
        {"buffer_before_minutes": -1},
        {"buffer_after_minutes": -1},
        {"price_cents": -1},
        {"currency": "EU"},
    ],
)
def test_service_dto_rejects_invalid_constraints(
    client: TestClient,
    invalid_fields: dict[str, object],
) -> None:
    _, headers, _, _, _ = setup_owner(client)
    payload: dict[str, object] = {
        "name": "Invalid Service",
        "duration_minutes": 30,
        "buffer_before_minutes": 0,
        "buffer_after_minutes": 0,
        "price_cents": 0,
        "currency": "EUR",
    }
    payload.update(invalid_fields)

    response = client.post("/api/v1/services", headers=headers, json=payload)
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT


def test_service_and_location_are_tenant_scoped(client: TestClient) -> None:
    _, first_headers, _, first_location, _ = setup_owner(client)
    first_service = create_service(
        client,
        first_headers,
        location_id=first_location["id"],
    )
    _, second_headers, _, second_location, _ = setup_owner(
        client,
        email="second-service-owner@example.com",
        tenant_name="Second Service Tenant",
        tenant_slug="second-service-tenant",
        location_slug="second-service-location",
    )
    second_service = create_service(
        client,
        second_headers,
        location_id=second_location["id"],
        name="Second Service",
    )

    foreign_location = client.post(
        "/api/v1/services",
        headers=first_headers,
        json={
            "location_id": second_location["id"],
            "name": "Foreign Location Service",
            "duration_minutes": 30,
        },
    )
    assert foreign_location.status_code == status.HTTP_404_NOT_FOUND
    assert foreign_location.json()["error"]["code"] == "location_not_found"

    hidden = client.get(
        f"/api/v1/services/{second_service['id']}",
        headers=first_headers,
    )
    assert hidden.status_code == status.HTTP_404_NOT_FOUND
    assert hidden.json()["error"]["code"] == "service_not_found"

    visible = client.get(
        f"/api/v1/services/{first_service['id']}",
        headers=first_headers,
    )
    assert visible.status_code == status.HTTP_200_OK


def test_employee_service_upsert_list_deactivate_and_reactivate(
    client: TestClient,
    session: Session,
) -> None:
    _, headers, _, location, employee = setup_owner(client)
    service = create_service(client, headers, location_id=location["id"])
    association_url = (
        f"/api/v1/employees/{employee['id']}/services/{service['id']}"
    )

    created = client.put(
        association_url,
        headers=headers,
        json={"custom_duration_minutes": 40, "custom_price_cents": 6500},
    )
    assert created.status_code == status.HTTP_200_OK
    assert created.json()["custom_duration_minutes"] == 40
    assert created.json()["custom_price_cents"] == 6500
    assert created.json()["is_active"] is True

    updated = client.put(
        association_url,
        headers=headers,
        json={"custom_duration_minutes": 50, "custom_price_cents": None},
    )
    assert updated.status_code == status.HTTP_200_OK
    assert updated.json()["custom_duration_minutes"] == 50
    assert updated.json()["custom_price_cents"] is None
    assert session.query(EmployeeService).count() == 1

    listed = client.get(
        f"/api/v1/employees/{employee['id']}/services",
        headers=headers,
    )
    assert listed.status_code == status.HTTP_200_OK
    assert len(listed.json()) == 1

    deleted = client.delete(association_url, headers=headers)
    assert deleted.status_code == status.HTTP_200_OK
    assert deleted.json()["is_active"] is False

    reactivated = client.put(association_url, headers=headers, json={})
    assert reactivated.status_code == status.HTTP_200_OK
    assert reactivated.json()["is_active"] is True
    assert reactivated.json()["custom_duration_minutes"] is None


@pytest.mark.parametrize(
    "payload",
    [
        {"custom_duration_minutes": 0},
        {"custom_price_cents": -1},
    ],
)
def test_employee_service_dto_rejects_invalid_custom_values(
    client: TestClient,
    payload: dict[str, int],
) -> None:
    _, headers, _, location, employee = setup_owner(client)
    service = create_service(client, headers, location_id=location["id"])

    response = client.put(
        f"/api/v1/employees/{employee['id']}/services/{service['id']}",
        headers=headers,
        json=payload,
    )
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT


def test_employee_service_rejects_cross_tenant_associations(
    client: TestClient,
) -> None:
    _, first_headers, _, first_location, first_employee = setup_owner(client)
    first_service = create_service(
        client,
        first_headers,
        location_id=first_location["id"],
    )
    _, second_headers, _, second_location, second_employee = setup_owner(
        client,
        email="association-owner@example.com",
        tenant_name="Association Tenant",
        tenant_slug="association-tenant",
        location_slug="association-location",
    )
    second_service = create_service(
        client,
        second_headers,
        location_id=second_location["id"],
        name="Association Service",
    )

    foreign_service = client.put(
        f"/api/v1/employees/{first_employee['id']}/services/"
        f"{second_service['id']}",
        headers=first_headers,
        json={},
    )
    assert foreign_service.status_code == status.HTTP_404_NOT_FOUND
    assert foreign_service.json()["error"]["code"] == "service_not_found"

    foreign_employee = client.put(
        f"/api/v1/employees/{second_employee['id']}/services/"
        f"{first_service['id']}",
        headers=first_headers,
        json={},
    )
    assert foreign_employee.status_code == status.HTTP_404_NOT_FOUND
    assert foreign_employee.json()["error"]["code"] == "employee_not_found"


def test_service_and_association_role_permissions(
    client: TestClient,
    session: Session,
) -> None:
    _, owner_headers, tenant, location, employee = setup_owner(client)
    role_headers: dict[MembershipRole, dict[str, str]] = {}

    for role in (
        MembershipRole.ADMIN,
        MembershipRole.MANAGER,
        MembershipRole.STAFF,
    ):
        email = f"service-{role.value}@example.com"
        auth_headers = create_user_headers(client, email)
        add_membership(
            session,
            tenant_id=tenant["id"],
            email=email,
            role=role,
        )
        role_headers[role] = tenant_headers(auth_headers, tenant["id"])

    service = create_service(
        client,
        role_headers[MembershipRole.ADMIN],
        location_id=location["id"],
    )
    manager_update = client.patch(
        f"/api/v1/services/{service['id']}",
        headers=role_headers[MembershipRole.MANAGER],
        json={"duration_minutes": 35},
    )
    assert manager_update.status_code == status.HTTP_200_OK

    manager_association = client.put(
        f"/api/v1/employees/{employee['id']}/services/{service['id']}",
        headers=role_headers[MembershipRole.MANAGER],
        json={},
    )
    assert manager_association.status_code == status.HTTP_200_OK

    staff_read = client.get(
        f"/api/v1/services/{service['id']}",
        headers=role_headers[MembershipRole.STAFF],
    )
    assert staff_read.status_code == status.HTTP_200_OK
    staff_associations = client.get(
        f"/api/v1/employees/{employee['id']}/services",
        headers=role_headers[MembershipRole.STAFF],
    )
    assert staff_associations.status_code == status.HTTP_200_OK

    staff_write = client.patch(
        f"/api/v1/services/{service['id']}",
        headers=role_headers[MembershipRole.STAFF],
        json={"duration_minutes": 40},
    )
    assert staff_write.status_code == status.HTTP_403_FORBIDDEN
    staff_link = client.put(
        f"/api/v1/employees/{employee['id']}/services/{service['id']}",
        headers=role_headers[MembershipRole.STAFF],
        json={},
    )
    assert staff_link.status_code == status.HTTP_403_FORBIDDEN

    owner_delete = client.delete(
        f"/api/v1/services/{service['id']}",
        headers=owner_headers,
    )
    assert owner_delete.status_code == status.HTTP_200_OK


@pytest.mark.parametrize(
    "invalid_field",
    [
        {"buffer_before_minutes": -1},
        {"buffer_after_minutes": -1},
        {"price_cents": -1},
        {"currency": "EU"},
    ],
)
def test_service_sql_constraints(
    session: Session,
    invalid_field: dict[str, object],
) -> None:
    tenant = Tenant(name="SQL Service Tenant", slug="sql-service-tenant")
    location = Location(name="SQL Location", slug="sql-location", tenant=tenant)
    session.add(location)
    session.flush()
    values: dict[str, object] = {
        "tenant_id": tenant.id,
        "location_id": location.id,
        "name": "Invalid SQL Service",
        "duration_minutes": 30,
        "buffer_before_minutes": 0,
        "buffer_after_minutes": 0,
        "price_cents": 0,
        "currency": "EUR",
    }
    values.update(invalid_field)

    with pytest.raises(IntegrityError), session.begin_nested():
        session.add(Service(**values))
        session.flush()


@pytest.mark.parametrize(
    "invalid_field",
    [
        {"custom_duration_minutes": 0},
        {"custom_price_cents": -1},
    ],
)
def test_employee_service_sql_constraints(
    session: Session,
    invalid_field: dict[str, int],
) -> None:
    tenant = Tenant(name="SQL Association Tenant", slug="sql-association-tenant")
    location = Location(name="SQL Location", slug="sql-location", tenant=tenant)
    employee = Employee(
        tenant=tenant,
        location=location,
        first_name="SQL",
        last_name="Employee",
    )
    service = Service(
        tenant=tenant,
        location=location,
        name="SQL Service",
        duration_minutes=30,
    )
    session.add_all([employee, service])
    session.flush()

    with pytest.raises(IntegrityError), session.begin_nested():
        session.add(
            EmployeeService(
                employee_id=employee.id,
                service_id=service.id,
                **invalid_field,
            )
        )
        session.flush()
