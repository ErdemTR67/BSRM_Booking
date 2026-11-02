from datetime import date, datetime, time
from uuid import UUID
from zoneinfo import ZoneInfo

from fastapi import status
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.appointment import Appointment, AppointmentStatus
from app.models.employee import Employee
from app.models.employee_availability import EmployeeAvailability
from app.models.employee_service import EmployeeService
from app.models.location_closure import LocationClosure
from app.models.opening_hour import OpeningHour
from app.models.service import Service
from app.models.time_off import TimeOff, TimeOffStatus
from tests.support import create_owned_tenant, create_user_headers


PASSWORD = "correct-horse-battery-staple"
TARGET_DATE = date(2026, 8, 10)  # Monday


def _setup(
    client: TestClient,
    session: Session,
    *,
    email: str = "availability-engine@example.com",
    slug: str = "availability-engine",
    timezone: str = "Europe/Brussels",
    associate: bool = True,
) -> tuple[dict[str, str], Employee, Service]:
    auth = create_user_headers(
        client, email, first_name="Engine", last_name="Tester"
    )
    tenant = create_owned_tenant(client, auth, name=slug, slug=slug)
    location = client.post(
        f"/api/v1/tenants/{tenant['id']}/locations",
        headers=auth,
        json={"name": "Main", "slug": f"{slug}-main", "timezone": timezone},
    ).json()
    headers = {**auth, "X-Tenant-ID": tenant["id"]}
    employee_data = client.post(
        "/api/v1/employees",
        headers=headers,
        json={
            "location_id": location["id"],
            "first_name": "Ada",
            "last_name": "Lovelace",
        },
    ).json()
    service_data = client.post(
        "/api/v1/services",
        headers=headers,
        json={
            "location_id": location["id"],
            "name": "Consultation",
            "duration_minutes": 30,
        },
    ).json()
    if associate:
        assert client.put(
            f"/api/v1/employees/{employee_data['id']}/services/{service_data['id']}",
            headers=headers,
            json={},
        ).status_code == status.HTTP_200_OK
    employee = session.get(Employee, UUID(employee_data["id"]))
    service = session.get(Service, UUID(service_data["id"]))
    assert employee is not None and service is not None
    return headers, employee, service


def _schedule(
    session: Session,
    employee: Employee,
    *,
    openings: list[tuple[time, time]] | None = None,
    availability: tuple[time, time] = (time(9), time(12)),
) -> None:
    for starts_at, ends_at in openings or [(time(9), time(12))]:
        session.add(
            OpeningHour(
                tenant_id=employee.tenant_id,
                location_id=employee.location_id,
                weekday=TARGET_DATE.weekday(),
                starts_at=starts_at,
                ends_at=ends_at,
            )
        )
    session.add(
        EmployeeAvailability(
            tenant_id=employee.tenant_id,
            employee_id=employee.id,
            weekday=TARGET_DATE.weekday(),
            starts_at=availability[0],
            ends_at=availability[1],
            valid_from=TARGET_DATE,
            valid_until=TARGET_DATE,
        )
    )
    session.commit()


def _url(employee: Employee, service: Service, **extra: str) -> str:
    params = {
        "location_id": str(employee.location_id),
        "employee_id": str(employee.id),
        "service_id": str(service.id),
        "date": TARGET_DATE.isoformat(),
        **extra,
    }
    return "/api/v1/availability?" + "&".join(f"{key}={value}" for key, value in params.items())


def test_standard_hours_and_grid(client: TestClient, session: Session) -> None:
    headers, employee, service = _setup(client, session)
    _schedule(session, employee)
    response = client.get(_url(employee, service), headers=headers)
    assert response.status_code == status.HTTP_200_OK
    slots = response.json()
    assert len(slots) == 11
    assert slots[0]["starts_at"].endswith("+02:00")
    assert slots[0]["starts_at"].startswith("2026-08-10T09:00:00")
    assert slots[-1]["starts_at"].startswith("2026-08-10T11:30:00")


def test_multiple_opening_ranges(client: TestClient, session: Session) -> None:
    headers, employee, service = _setup(client, session)
    _schedule(
        session,
        employee,
        openings=[(time(9), time(10)), (time(11), time(12))],
    )
    slots = client.get(
        _url(employee, service, slot_interval_minutes="30"), headers=headers
    ).json()
    assert [item["starts_at"][11:16] for item in slots] == ["09:00", "09:30", "11:00", "11:30"]


def test_closure_removes_overlapping_slots(client: TestClient, session: Session) -> None:
    headers, employee, service = _setup(client, session)
    _schedule(session, employee)
    timezone = ZoneInfo("Europe/Brussels")
    session.add(
        LocationClosure(
            tenant_id=employee.tenant_id,
            location_id=employee.location_id,
            starts_at=datetime(2026, 8, 10, 10, 0, tzinfo=timezone),
            ends_at=datetime(2026, 8, 10, 11, 0, tzinfo=timezone),
        )
    )
    session.commit()
    starts = [
        item["starts_at"][11:16]
        for item in client.get(_url(employee, service), headers=headers).json()
    ]
    assert "09:45" not in starts
    assert "10:00" not in starts
    assert "10:30" not in starts
    assert "11:00" in starts


def test_only_approved_time_off_blocks(client: TestClient, session: Session) -> None:
    headers, employee, service = _setup(client, session)
    _schedule(session, employee)
    timezone = ZoneInfo("Europe/Brussels")
    session.add_all(
        [
            TimeOff(
                tenant_id=employee.tenant_id,
                employee_id=employee.id,
                starts_at=datetime(2026, 8, 10, 9, 0, tzinfo=timezone),
                ends_at=datetime(2026, 8, 10, 10, 0, tzinfo=timezone),
                status=TimeOffStatus.APPROVED.value,
            ),
            TimeOff(
                tenant_id=employee.tenant_id,
                employee_id=employee.id,
                starts_at=datetime(2026, 8, 10, 11, 0, tzinfo=timezone),
                ends_at=datetime(2026, 8, 10, 12, 0, tzinfo=timezone),
                status=TimeOffStatus.PENDING.value,
            ),
        ]
    )
    session.commit()
    starts = [
        item["starts_at"][11:16]
        for item in client.get(_url(employee, service), headers=headers).json()
    ]
    assert starts[0] == "10:00"
    assert "11:00" in starts


def test_active_appointment_blocks_but_cancelled_does_not(
    client: TestClient,
    session: Session,
) -> None:
    headers, employee, service = _setup(client, session)
    _schedule(session, employee)
    timezone = ZoneInfo("Europe/Brussels")
    session.add_all(
        [
            Appointment(
                tenant_id=employee.tenant_id,
                location_id=employee.location_id,
                employee_id=employee.id,
                starts_at=datetime(2026, 8, 10, 9, 30, tzinfo=timezone),
                ends_at=datetime(2026, 8, 10, 10, 0, tzinfo=timezone),
                status=AppointmentStatus.PENDING.value,
                customer_name="Pending Customer",
            ),
            Appointment(
                tenant_id=employee.tenant_id,
                location_id=employee.location_id,
                employee_id=employee.id,
                starts_at=datetime(2026, 8, 10, 10, 30, tzinfo=timezone),
                ends_at=datetime(2026, 8, 10, 11, 0, tzinfo=timezone),
                status=AppointmentStatus.CANCELLED.value,
                customer_name="Cancelled Customer",
            ),
        ]
    )
    session.commit()
    starts = [
        item["starts_at"][11:16]
        for item in client.get(_url(employee, service), headers=headers).json()
    ]
    assert "09:15" not in starts
    assert "09:30" not in starts
    assert "10:30" in starts


def test_buffers_and_custom_duration_are_in_occupied_interval(
    client: TestClient,
    session: Session,
) -> None:
    headers, employee, service = _setup(client, session)
    _schedule(session, employee, availability=(time(9), time(11)))
    association = session.get(EmployeeService, (employee.id, service.id))
    assert association is not None
    association.custom_duration_minutes = 40
    service.buffer_before_minutes = 5
    service.buffer_after_minutes = 10
    session.commit()

    slots = client.get(
        _url(employee, service, slot_interval_minutes="30"), headers=headers
    ).json()
    assert [item["starts_at"][11:16] for item in slots] == ["09:00", "09:30", "10:00"]
    assert slots[0]["ends_at"][11:16] == "09:55"
    assert slots[0]["duration_minutes"] == 40
    assert slots[0]["buffer_before_minutes"] == 5
    assert slots[0]["buffer_after_minutes"] == 10


def test_unassociated_employee_has_no_slots(client: TestClient, session: Session) -> None:
    headers, employee, service = _setup(client, session, associate=False)
    _schedule(session, employee)
    assert client.get(_url(employee, service), headers=headers).json() == []


def test_availability_outside_validity_period_is_ignored(
    client: TestClient,
    session: Session,
) -> None:
    headers, employee, service = _setup(client, session)
    session.add_all(
        [
            OpeningHour(
                tenant_id=employee.tenant_id,
                location_id=employee.location_id,
                weekday=TARGET_DATE.weekday(),
                starts_at=time(9),
                ends_at=time(12),
            ),
            EmployeeAvailability(
                tenant_id=employee.tenant_id,
                employee_id=employee.id,
                weekday=TARGET_DATE.weekday(),
                starts_at=time(9),
                ends_at=time(12),
                valid_from=date(2026, 8, 11),
            ),
        ]
    )
    session.commit()
    assert client.get(_url(employee, service), headers=headers).json() == []


def test_eligible_employees_are_returned_when_employee_is_omitted(
    client: TestClient,
    session: Session,
) -> None:
    headers, employee, service = _setup(client, session)
    _schedule(session, employee, availability=(time(9), time(10)))
    url = (
        "/api/v1/availability"
        f"?location_id={employee.location_id}&service_id={service.id}&date={TARGET_DATE}"
    )
    slots = client.get(url, headers=headers).json()
    assert {item["employee_id"] for item in slots} == {str(employee.id)}


def test_availability_is_tenant_scoped(client: TestClient, session: Session) -> None:
    first_headers, _, _ = _setup(client, session)
    second_headers, second_employee, second_service = _setup(
        client,
        session,
        email="availability-foreign@example.com",
        slug="availability-foreign",
    )
    _schedule(session, second_employee)
    response = client.get(_url(second_employee, second_service), headers=first_headers)
    assert response.status_code == status.HTTP_404_NOT_FOUND
    assert response.json()["error"]["code"] == "location_not_found"
    assert client.get(
        _url(second_employee, second_service), headers=second_headers
    ).status_code == status.HTTP_200_OK
