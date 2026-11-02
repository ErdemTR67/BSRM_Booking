from datetime import time
from uuid import UUID

from fastapi import status
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.employee import Employee
from app.models.employee_availability import EmployeeAvailability
from app.models.employee_service import EmployeeService
from app.models.location import Location
from app.models.opening_hour import OpeningHour
from app.models.service import Service
from tests.support import create_owned_tenant, create_user_headers


def _tenant_headers(
    client: TestClient,
    *,
    email: str,
    slug: str,
) -> tuple[dict[str, str], UUID]:
    auth = create_user_headers(client, email)
    tenant = create_owned_tenant(client, auth, name=slug, slug=slug)
    tenant_id = UUID(str(tenant["id"]))
    return {**auth, "X-Tenant-ID": str(tenant_id)}, tenant_id


def _create_booking_configuration(
    session: Session,
    tenant_id: UUID,
    *,
    availability_starts_at: time = time(9),
    availability_ends_at: time = time(18),
) -> Employee:
    location = Location(
        tenant_id=tenant_id,
        name="Main location",
        slug="main-location",
        timezone="Europe/Brussels",
    )
    employee = Employee(
        tenant_id=tenant_id,
        location=location,
        first_name="Ada",
        last_name="Lovelace",
        is_bookable=True,
    )
    service = Service(
        tenant_id=tenant_id,
        location=location,
        name="Consultation",
        duration_minutes=30,
        buffer_before_minutes=5,
        buffer_after_minutes=5,
        currency="EUR",
    )
    session.add_all([location, employee, service])
    session.flush()
    session.add_all(
        [
            OpeningHour(
                tenant_id=tenant_id,
                location_id=location.id,
                weekday=0,
                starts_at=time(9),
                ends_at=time(18),
            ),
            EmployeeService(
                employee_id=employee.id,
                service_id=service.id,
                is_active=True,
            ),
            EmployeeAvailability(
                tenant_id=tenant_id,
                employee_id=employee.id,
                weekday=0,
                starts_at=availability_starts_at,
                ends_at=availability_ends_at,
            ),
        ]
    )
    session.commit()
    return employee


def test_setup_status_requires_authentication(client: TestClient) -> None:
    response = client.get(
        "/api/v1/setup/status",
        headers={"X-Tenant-ID": "11111111-1111-4111-8111-111111111111"},
    )

    assert response.status_code == status.HTTP_401_UNAUTHORIZED


def test_empty_tenant_reports_first_step(client: TestClient) -> None:
    headers, _ = _tenant_headers(
        client,
        email="empty-setup@example.com",
        slug="empty-setup",
    )

    response = client.get("/api/v1/setup/status", headers=headers)

    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {
        "is_complete": False,
        "progress_percent": 0,
        "next_step": "location",
        "steps": [
            {"key": "location", "complete": False},
            {"key": "opening_hours", "complete": False},
            {"key": "service", "complete": False},
            {"key": "employee", "complete": False},
            {"key": "employee_service", "complete": False},
            {"key": "employee_availability", "complete": False},
        ],
    }


def test_complete_booking_configuration_is_ready(
    client: TestClient,
    session: Session,
) -> None:
    headers, tenant_id = _tenant_headers(
        client,
        email="complete-setup@example.com",
        slug="complete-setup",
    )
    _create_booking_configuration(session, tenant_id)

    response = client.get("/api/v1/setup/status", headers=headers)

    assert response.status_code == status.HTTP_200_OK
    body = response.json()
    assert body["is_complete"] is True
    assert body["progress_percent"] == 100
    assert body["next_step"] is None
    assert all(step["complete"] for step in body["steps"])


def test_availability_must_fit_the_service_duration(
    client: TestClient,
    session: Session,
) -> None:
    headers, tenant_id = _tenant_headers(
        client,
        email="short-schedule@example.com",
        slug="short-schedule",
    )
    _create_booking_configuration(
        session,
        tenant_id,
        availability_starts_at=time(17, 45),
        availability_ends_at=time(18),
    )

    response = client.get("/api/v1/setup/status", headers=headers)

    assert response.status_code == status.HTTP_200_OK
    body = response.json()
    assert body["is_complete"] is False
    assert body["progress_percent"] == 83
    assert body["next_step"] == "employee_availability"
    assert body["steps"][-1] == {
        "key": "employee_availability",
        "complete": False,
    }


def test_inactive_employee_breaks_the_bookable_chain(
    client: TestClient,
    session: Session,
) -> None:
    headers, tenant_id = _tenant_headers(
        client,
        email="inactive-employee-setup@example.com",
        slug="inactive-employee-setup",
    )
    employee = _create_booking_configuration(session, tenant_id)
    employee.is_active = False
    session.commit()

    response = client.get("/api/v1/setup/status", headers=headers)

    assert response.status_code == status.HTTP_200_OK
    body = response.json()
    assert body["is_complete"] is False
    assert body["progress_percent"] == 50
    assert body["next_step"] == "employee"


def test_setup_status_is_isolated_by_tenant(
    client: TestClient,
    session: Session,
) -> None:
    empty_headers, _ = _tenant_headers(
        client,
        email="isolated-empty@example.com",
        slug="isolated-empty",
    )
    _, configured_tenant_id = _tenant_headers(
        client,
        email="isolated-complete@example.com",
        slug="isolated-complete",
    )
    _create_booking_configuration(session, configured_tenant_id)

    response = client.get("/api/v1/setup/status", headers=empty_headers)

    assert response.status_code == status.HTTP_200_OK
    assert response.json()["progress_percent"] == 0
    assert response.json()["is_complete"] is False
