from datetime import date, datetime, time, timezone
from uuid import UUID

import pytest
from fastapi import status
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.employee import Employee
from app.models.employee_availability import EmployeeAvailability
from app.models.location import Location
from app.models.membership import Membership, MembershipRole
from app.models.tenant import Tenant
from app.models.time_off import TimeOff
from app.models.user import User
from tests.support import create_owned_tenant, create_user_headers


PASSWORD = "correct-horse-battery-staple"


def _auth_headers(client: TestClient, email: str) -> dict[str, str]:
    return create_user_headers(
        client, email, first_name="Availability", last_name="Tester"
    )


def _setup_owner(
    client: TestClient,
    *,
    email: str = "availability-owner@example.com",
    slug: str = "availability-tenant",
) -> tuple[dict[str, str], dict[str, object], dict[str, object]]:
    auth = _auth_headers(client, email)
    tenant = create_owned_tenant(
        client,
        auth,
        name=slug.replace("-", " ").title(),
        slug=slug,
    )
    location_response = client.post(
        f"/api/v1/tenants/{tenant['id']}/locations",
        headers=auth,
        json={"name": "Main", "slug": f"{slug}-main"},
    )
    assert location_response.status_code == status.HTTP_201_CREATED
    headers = {**auth, "X-Tenant-ID": tenant["id"]}
    employee_response = client.post(
        "/api/v1/employees",
        headers=headers,
        json={
            "location_id": location_response.json()["id"],
            "first_name": "Ada",
            "last_name": "Lovelace",
        },
    )
    assert employee_response.status_code == status.HTTP_201_CREATED
    return headers, tenant, employee_response.json()


def _add_role(
    client: TestClient,
    session: Session,
    tenant_id: str,
    role: MembershipRole,
) -> dict[str, str]:
    email = f"availability-{role.value}@example.com"
    auth = _auth_headers(client, email)
    user = session.scalar(select(User).where(User.email == email))
    assert user is not None
    session.add(
        Membership(
            tenant_id=UUID(tenant_id),
            user_id=user.id,
            role=role.value,
            is_active=True,
        )
    )
    session.commit()
    return {**auth, "X-Tenant-ID": tenant_id}


def test_employee_availability_crud_and_soft_deactivation(client: TestClient) -> None:
    headers, _, employee = _setup_owner(client)
    base_url = f"/api/v1/employees/{employee['id']}/availabilities"
    created = client.post(
        base_url,
        headers=headers,
        json={
            "weekday": 1,
            "starts_at": "09:00",
            "ends_at": "17:00",
            "valid_from": "2026-01-01",
            "valid_until": "2026-12-31",
        },
    )
    assert created.status_code == status.HTTP_201_CREATED
    availability = created.json()
    assert "tenant_id" not in availability
    assert client.get(f"{base_url}/{availability['id']}", headers=headers).status_code == 200

    patched = client.patch(
        f"{base_url}/{availability['id']}",
        headers=headers,
        json={"ends_at": "18:00", "valid_until": None},
    )
    assert patched.status_code == status.HTTP_200_OK
    assert patched.json()["ends_at"] == "18:00:00"
    assert patched.json()["valid_until"] is None

    deleted = client.delete(f"{base_url}/{availability['id']}", headers=headers)
    assert deleted.status_code == status.HTTP_200_OK
    assert deleted.json()["is_active"] is False
    assert client.get(base_url, headers=headers).json() == []


@pytest.mark.parametrize(
    "payload",
    [
        {"weekday": 7, "starts_at": "09:00", "ends_at": "17:00"},
        {"weekday": 1, "starts_at": "17:00", "ends_at": "09:00"},
        {
            "weekday": 1,
            "starts_at": "09:00",
            "ends_at": "17:00",
            "valid_from": "2026-12-31",
            "valid_until": "2026-01-01",
        },
    ],
)
def test_availability_dto_rejects_invalid_ranges(
    client: TestClient,
    payload: dict[str, object],
) -> None:
    headers, _, employee = _setup_owner(client)
    response = client.post(
        f"/api/v1/employees/{employee['id']}/availabilities",
        headers=headers,
        json=payload,
    )
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT


def test_availability_partial_update_revalidates_dates(client: TestClient) -> None:
    headers, _, employee = _setup_owner(client)
    base_url = f"/api/v1/employees/{employee['id']}/availabilities"
    availability = client.post(
        base_url,
        headers=headers,
        json={
            "weekday": 2,
            "starts_at": "09:00",
            "ends_at": "17:00",
            "valid_from": "2026-01-01",
            "valid_until": "2026-06-30",
        },
    ).json()
    response = client.patch(
        f"{base_url}/{availability['id']}",
        headers=headers,
        json={"valid_from": "2026-07-01"},
    )
    assert response.status_code == status.HTTP_400_BAD_REQUEST


def test_time_off_statuses_filtering_and_cancellation(client: TestClient) -> None:
    headers, _, employee = _setup_owner(client)
    base_url = f"/api/v1/employees/{employee['id']}/time-off"
    created = client.post(
        base_url,
        headers=headers,
        json={
            "starts_at": "2026-07-01T09:00:00+02:00",
            "ends_at": "2026-07-03T18:00:00+02:00",
            "reason": "Leave",
        },
    )
    assert created.status_code == status.HTTP_201_CREATED
    entry = created.json()
    assert entry["status"] == "pending"

    for expected_status in ("approved", "rejected", "pending"):
        updated = client.patch(
            f"{base_url}/{entry['id']}",
            headers=headers,
            json={"status": expected_status},
        )
        assert updated.status_code == status.HTTP_200_OK
        assert updated.json()["status"] == expected_status

    approved = client.patch(
        f"{base_url}/{entry['id']}",
        headers=headers,
        json={"status": "approved"},
    )
    assert approved.status_code == status.HTTP_200_OK
    assert len(client.get(f"{base_url}?status=approved", headers=headers).json()) == 1
    assert client.get(f"{base_url}?status=rejected", headers=headers).json() == []
    naive_patch = client.patch(
        f"{base_url}/{entry['id']}",
        headers=headers,
        json={"starts_at": "2026-07-01T10:00:00"},
    )
    assert naive_patch.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT

    cancelled = client.delete(f"{base_url}/{entry['id']}", headers=headers)
    assert cancelled.status_code == status.HTTP_200_OK
    assert cancelled.json()["status"] == "cancelled"


@pytest.mark.parametrize(
    "payload",
    [
        {
            "starts_at": "2026-07-03T18:00:00+02:00",
            "ends_at": "2026-07-01T09:00:00+02:00",
        },
        {
            "starts_at": "2026-07-01T09:00:00+02:00",
            "ends_at": "2026-07-03T18:00:00+02:00",
            "status": "unknown",
        },
        {
            "starts_at": "2026-07-01T09:00:00",
            "ends_at": "2026-07-03T18:00:00",
        },
    ],
)
def test_time_off_dto_rejects_invalid_data(
    client: TestClient,
    payload: dict[str, object],
) -> None:
    headers, _, employee = _setup_owner(client)
    response = client.post(
        f"/api/v1/employees/{employee['id']}/time-off",
        headers=headers,
        json=payload,
    )
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT


def test_availability_and_time_off_are_tenant_scoped(client: TestClient) -> None:
    first_headers, _, first_employee = _setup_owner(client)
    second_headers, _, second_employee = _setup_owner(
        client,
        email="availability-second@example.com",
        slug="availability-second-tenant",
    )
    availability = client.post(
        f"/api/v1/employees/{second_employee['id']}/availabilities",
        headers=second_headers,
        json={"weekday": 3, "starts_at": "09:00", "ends_at": "17:00"},
    ).json()
    time_off = client.post(
        f"/api/v1/employees/{second_employee['id']}/time-off",
        headers=second_headers,
        json={
            "starts_at": "2026-08-01T09:00:00+02:00",
            "ends_at": "2026-08-02T18:00:00+02:00",
        },
    ).json()

    assert client.get(
        f"/api/v1/employees/{second_employee['id']}/availabilities",
        headers=first_headers,
    ).status_code == status.HTTP_404_NOT_FOUND
    assert client.get(
        f"/api/v1/employees/{first_employee['id']}/availabilities/{availability['id']}",
        headers=first_headers,
    ).status_code == status.HTTP_404_NOT_FOUND
    assert client.get(
        f"/api/v1/employees/{first_employee['id']}/time-off/{time_off['id']}",
        headers=first_headers,
    ).status_code == status.HTTP_404_NOT_FOUND


def test_availability_permissions(client: TestClient, session: Session) -> None:
    _, tenant, employee = _setup_owner(client)
    manager = _add_role(client, session, tenant["id"], MembershipRole.MANAGER)
    staff = _add_role(client, session, tenant["id"], MembershipRole.STAFF)
    url = f"/api/v1/employees/{employee['id']}/availabilities"
    created = client.post(
        url,
        headers=manager,
        json={"weekday": 4, "starts_at": "09:00", "ends_at": "17:00"},
    )
    assert created.status_code == status.HTTP_201_CREATED
    assert client.get(url, headers=staff).status_code == status.HTTP_200_OK
    assert client.post(
        url,
        headers=staff,
        json={"weekday": 5, "starts_at": "09:00", "ends_at": "17:00"},
    ).status_code == status.HTTP_403_FORBIDDEN


def test_phase_8_sql_constraints(session: Session) -> None:
    tenant = Tenant(name="Availability SQL", slug="availability-sql")
    location = Location(name="Main", slug="main", tenant=tenant)
    employee = Employee(
        tenant=tenant,
        location=location,
        first_name="SQL",
        last_name="Employee",
    )
    session.add(employee)
    session.flush()

    invalid_records = [
        EmployeeAvailability(
            tenant_id=tenant.id,
            employee_id=employee.id,
            weekday=7,
            starts_at=time(9),
            ends_at=time(17),
        ),
        EmployeeAvailability(
            tenant_id=tenant.id,
            employee_id=employee.id,
            weekday=1,
            starts_at=time(9),
            ends_at=time(17),
            valid_from=date(2026, 12, 31),
            valid_until=date(2026, 1, 1),
        ),
        TimeOff(
            tenant_id=tenant.id,
            employee_id=employee.id,
            starts_at=datetime(2026, 1, 2, tzinfo=timezone.utc),
            ends_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
            status="pending",
        ),
        TimeOff(
            tenant_id=tenant.id,
            employee_id=employee.id,
            starts_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
            ends_at=datetime(2026, 1, 2, tzinfo=timezone.utc),
            status="unknown",
        ),
    ]
    for record in invalid_records:
        with pytest.raises(IntegrityError), session.begin_nested():
            session.add(record)
            session.flush()
