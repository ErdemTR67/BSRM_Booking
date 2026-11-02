from datetime import date, datetime, time
from uuid import UUID
from zoneinfo import ZoneInfo

import pytest
from fastapi import status
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.appointment import AppointmentStatus
from app.models.customer import Customer
from app.models.employee import Employee
from app.models.employee_availability import EmployeeAvailability
from app.models.location_closure import LocationClosure
from app.models.membership import Membership, MembershipRole
from app.models.opening_hour import OpeningHour
from app.models.service import Service
from app.models.time_off import TimeOff, TimeOffStatus
from app.models.user import User
from tests.support import create_owned_tenant, create_user_headers


PASSWORD = "correct-horse-battery-staple"
TARGET_DATE = date(2026, 8, 10)
TZ = ZoneInfo("Europe/Brussels")


def _auth_headers(client: TestClient, email: str) -> dict[str, str]:
    return create_user_headers(
        client, email, first_name="Appointment", last_name="Tester"
    )


def _setup(
    client: TestClient,
    session: Session,
    *,
    email: str = "appointment-owner@example.com",
    slug: str = "appointment-tenant",
    associate: bool = True,
) -> tuple[dict[str, str], dict[str, object], Employee, Service]:
    auth = _auth_headers(client, email)
    tenant = create_owned_tenant(client, auth, name=slug, slug=slug)
    location = client.post(
        f"/api/v1/tenants/{tenant['id']}/locations",
        headers=auth,
        json={
            "name": "Main",
            "slug": f"{slug}-main",
            "timezone": "Europe/Brussels",
        },
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
            "buffer_before_minutes": 5,
            "buffer_after_minutes": 10,
            "price_cents": 4000,
        },
    ).json()
    if associate:
        assert client.put(
            f"/api/v1/employees/{employee_data['id']}/services/{service_data['id']}",
            headers=headers,
            json={"custom_duration_minutes": 40, "custom_price_cents": 5500},
        ).status_code == status.HTTP_200_OK
    employee = session.get(Employee, UUID(employee_data["id"]))
    service = session.get(Service, UUID(service_data["id"]))
    assert employee is not None and service is not None
    session.add_all(
        [
            OpeningHour(
                tenant_id=employee.tenant_id,
                location_id=employee.location_id,
                weekday=TARGET_DATE.weekday(),
                starts_at=time(8),
                ends_at=time(18),
            ),
            EmployeeAvailability(
                tenant_id=employee.tenant_id,
                employee_id=employee.id,
                weekday=TARGET_DATE.weekday(),
                starts_at=time(8),
                ends_at=time(18),
                valid_from=TARGET_DATE,
                valid_until=TARGET_DATE,
            ),
        ]
    )
    session.commit()
    return headers, tenant, employee, service


def _payload(
    employee: Employee,
    service: Service,
    *,
    hour: int = 9,
    minute: int = 0,
) -> dict[str, object]:
    return {
        "location_id": str(employee.location_id),
        "employee_id": str(employee.id),
        "service_ids": [str(service.id)],
        "starts_at": datetime(2026, 8, 10, hour, minute, tzinfo=TZ).isoformat(),
        "customer": {
            "first_name": "Grace",
            "last_name": "Hopper",
            "email": "GRACE@example.com",
            "phone": "+32123456789",
        },
        "notes": "First visit",
    }


def _create(
    client: TestClient,
    headers: dict[str, str],
    employee: Employee,
    service: Service,
    *,
    hour: int = 9,
    minute: int = 0,
) -> dict[str, object]:
    response = client.post(
        "/api/v1/appointments",
        headers=headers,
        json=_payload(employee, service, hour=hour, minute=minute),
    )
    assert response.status_code == status.HTTP_201_CREATED, response.text
    return response.json()


def _add_role(
    client: TestClient,
    session: Session,
    tenant_id: str,
    role: MembershipRole,
) -> dict[str, str]:
    email = f"appointment-{role.value}@example.com"
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


def test_create_calculates_end_customer_and_service_snapshots(
    client: TestClient,
    session: Session,
) -> None:
    headers, _, employee, service = _setup(client, session)
    appointment = _create(client, headers, employee, service)
    assert "tenant_id" not in appointment
    assert appointment["status"] == "pending"
    assert appointment["starts_at"].startswith("2026-08-10T09:00:00")
    assert appointment["ends_at"].startswith("2026-08-10T09:55:00")
    assert appointment["customer_name"] == "Grace Hopper"
    assert appointment["customer_email"] == "grace@example.com"
    assert appointment["customer_id"] is not None
    assert appointment["services"] == [
        {
            "id": appointment["services"][0]["id"],
            "service_id": str(service.id),
            "service_name": "Consultation",
            "duration_minutes": 40,
            "price_cents": 5500,
            "position": 0,
        }
    ]


def test_existing_customer_can_be_linked(client: TestClient, session: Session) -> None:
    headers, _, employee, service = _setup(client, session)
    customer = client.post(
        "/api/v1/customers",
        headers=headers,
        json={"first_name": "Existing", "last_name": "Customer"},
    ).json()
    payload = _payload(employee, service)
    payload.pop("customer")
    payload["customer_id"] = customer["id"]
    response = client.post("/api/v1/appointments", headers=headers, json=payload)
    assert response.status_code == status.HTTP_201_CREATED
    assert response.json()["customer_id"] == customer["id"]
    assert response.json()["customer_name"] == "Existing Customer"


def test_multiple_services_keep_ordered_effective_snapshots(
    client: TestClient,
    session: Session,
) -> None:
    headers, _, employee, first_service = _setup(client, session)
    second_response = client.post(
        "/api/v1/services",
        headers=headers,
        json={
            "location_id": str(employee.location_id),
            "name": "Follow-up",
            "duration_minutes": 20,
            "price_cents": 2000,
        },
    )
    assert second_response.status_code == status.HTTP_201_CREATED
    second_service = second_response.json()
    assert client.put(
        f"/api/v1/employees/{employee.id}/services/{second_service['id']}",
        headers=headers,
        json={},
    ).status_code == status.HTTP_200_OK
    payload = _payload(employee, first_service, hour=13)
    payload["service_ids"] = [str(first_service.id), second_service["id"]]
    response = client.post("/api/v1/appointments", headers=headers, json=payload)
    assert response.status_code == status.HTTP_201_CREATED
    appointment = response.json()
    assert appointment["ends_at"].startswith("2026-08-10T14:15:00")
    assert [item["position"] for item in appointment["services"]] == [0, 1]
    assert [item["duration_minutes"] for item in appointment["services"]] == [40, 20]


@pytest.mark.parametrize("field", ["ends_at", "status", "tenant_id", "price_cents"])
def test_create_rejects_backend_calculated_fields(
    client: TestClient,
    session: Session,
    field: str,
) -> None:
    headers, tenant, employee, service = _setup(client, session)
    payload = _payload(employee, service)
    payload[field] = tenant["id"] if field == "tenant_id" else "invalid"
    assert client.post(
        "/api/v1/appointments", headers=headers, json=payload
    ).status_code == status.HTTP_422_UNPROCESSABLE_CONTENT


def test_creation_requires_active_employee_service_association(
    client: TestClient,
    session: Session,
) -> None:
    headers, _, employee, service = _setup(client, session, associate=False)
    before = session.scalar(select(func.count()).select_from(Customer))
    response = client.post(
        "/api/v1/appointments",
        headers=headers,
        json=_payload(employee, service),
    )
    assert response.status_code == status.HTTP_404_NOT_FOUND
    assert response.json()["error"]["code"] == "service_not_found"
    assert session.scalar(select(func.count()).select_from(Customer)) == before


@pytest.mark.parametrize("blocker", ["closure", "time_off"])
def test_creation_respects_closures_and_approved_time_off(
    client: TestClient,
    session: Session,
    blocker: str,
) -> None:
    headers, _, employee, service = _setup(client, session)
    if blocker == "closure":
        session.add(
            LocationClosure(
                tenant_id=employee.tenant_id,
                location_id=employee.location_id,
                starts_at=datetime(2026, 8, 10, 9, 30, tzinfo=TZ),
                ends_at=datetime(2026, 8, 10, 10, 0, tzinfo=TZ),
            )
        )
    else:
        session.add(
            TimeOff(
                tenant_id=employee.tenant_id,
                employee_id=employee.id,
                starts_at=datetime(2026, 8, 10, 9, 30, tzinfo=TZ),
                ends_at=datetime(2026, 8, 10, 10, 0, tzinfo=TZ),
                status=TimeOffStatus.APPROVED.value,
            )
        )
    session.commit()
    response = client.post(
        "/api/v1/appointments",
        headers=headers,
        json=_payload(employee, service),
    )
    assert response.status_code == status.HTTP_409_CONFLICT
    assert response.json()["error"]["code"] == "appointment_conflict"


def test_creation_rejects_existing_appointment_overlap(
    client: TestClient,
    session: Session,
) -> None:
    headers, _, employee, service = _setup(client, session)
    _create(client, headers, employee, service)
    overlap = client.post(
        "/api/v1/appointments",
        headers=headers,
        json=_payload(employee, service, hour=9, minute=30),
    )
    assert overlap.status_code == status.HTTP_409_CONFLICT


def test_creation_must_fit_opening_and_employee_availability(
    client: TestClient,
    session: Session,
) -> None:
    headers, _, employee, service = _setup(client, session)
    response = client.post(
        "/api/v1/appointments",
        headers=headers,
        json=_payload(employee, service, hour=17, minute=30),
    )
    assert response.status_code == status.HTTP_409_CONFLICT


def test_list_filters_and_patch(client: TestClient, session: Session) -> None:
    headers, _, employee, service = _setup(client, session)
    appointment = _create(client, headers, employee, service)
    patched = client.patch(
        f"/api/v1/appointments/{appointment['id']}",
        headers=headers,
        json={"notes": "Updated notes"},
    )
    assert patched.status_code == status.HTTP_200_OK
    assert patched.json()["notes"] == "Updated notes"

    query = (
        f"?location_id={employee.location_id}&employee_id={employee.id}"
        f"&customer_id={appointment['customer_id']}&status=pending"
        "&date_from=2026-08-10T00:00:00%2B02:00"
        "&date_to=2026-08-11T00:00:00%2B02:00"
    )
    listed = client.get(f"/api/v1/appointments{query}", headers=headers)
    assert listed.status_code == status.HTTP_200_OK
    assert [item["id"] for item in listed.json()["items"]] == [appointment["id"]]
    assert listed.json()["total"] == 1
    assert listed.json()["page"] == 1
    assert listed.json()["page_size"] == 20


def test_status_transitions(client: TestClient, session: Session) -> None:
    headers, _, employee, service = _setup(client, session)
    completed = _create(client, headers, employee, service, hour=9)
    assert client.post(
        f"/api/v1/appointments/{completed['id']}/complete", headers=headers
    ).status_code == status.HTTP_409_CONFLICT
    confirmed = client.post(
        f"/api/v1/appointments/{completed['id']}/confirm", headers=headers
    )
    assert confirmed.json()["status"] == AppointmentStatus.CONFIRMED.value
    assert client.post(
        f"/api/v1/appointments/{completed['id']}/complete", headers=headers
    ).json()["status"] == AppointmentStatus.COMPLETED.value

    cancelled = _create(client, headers, employee, service, hour=10)
    cancellation = client.post(
        f"/api/v1/appointments/{cancelled['id']}/cancel",
        headers=headers,
        json={"cancellation_reason": "Customer request"},
    )
    assert cancellation.json()["status"] == AppointmentStatus.CANCELLED.value
    assert cancellation.json()["cancellation_reason"] == "Customer request"

    no_show = _create(client, headers, employee, service, hour=11)
    client.post(f"/api/v1/appointments/{no_show['id']}/confirm", headers=headers)
    assert client.post(
        f"/api/v1/appointments/{no_show['id']}/mark-no-show", headers=headers
    ).json()["status"] == AppointmentStatus.NO_SHOW.value

    confirmed_cancel = _create(client, headers, employee, service, hour=12)
    client.post(
        f"/api/v1/appointments/{confirmed_cancel['id']}/confirm", headers=headers
    )
    assert client.post(
        f"/api/v1/appointments/{confirmed_cancel['id']}/cancel", headers=headers
    ).json()["status"] == AppointmentStatus.CANCELLED.value


def test_appointments_are_tenant_scoped(client: TestClient, session: Session) -> None:
    first_headers, _, _, _ = _setup(client, session)
    second_headers, _, second_employee, second_service = _setup(
        client,
        session,
        email="appointment-foreign@example.com",
        slug="appointment-foreign",
    )
    appointment = _create(client, second_headers, second_employee, second_service)
    response = client.get(
        f"/api/v1/appointments/{appointment['id']}", headers=first_headers
    )
    assert response.status_code == status.HTTP_404_NOT_FOUND


def test_creation_rejects_foreign_tenant_references(
    client: TestClient,
    session: Session,
) -> None:
    first_headers, _, first_employee, first_service = _setup(client, session)
    second_headers, _, second_employee, second_service = _setup(
        client,
        session,
        email="appointment-reference-foreign@example.com",
        slug="appointment-reference-foreign",
    )
    foreign_customer = client.post(
        "/api/v1/customers",
        headers=second_headers,
        json={"first_name": "Foreign", "last_name": "Customer"},
    ).json()

    foreign_location = client.post(
        "/api/v1/appointments",
        headers=first_headers,
        json=_payload(second_employee, second_service),
    )
    assert foreign_location.status_code == status.HTTP_404_NOT_FOUND
    assert foreign_location.json()["error"]["code"] == "location_not_found"

    foreign_service_payload = _payload(first_employee, first_service, hour=12)
    foreign_service_payload["service_ids"] = [str(second_service.id)]
    foreign_service = client.post(
        "/api/v1/appointments", headers=first_headers, json=foreign_service_payload
    )
    assert foreign_service.status_code == status.HTTP_404_NOT_FOUND
    assert foreign_service.json()["error"]["code"] == "service_not_found"

    foreign_customer_payload = _payload(first_employee, first_service, hour=12)
    foreign_customer_payload.pop("customer")
    foreign_customer_payload["customer_id"] = foreign_customer["id"]
    customer_response = client.post(
        "/api/v1/appointments", headers=first_headers, json=foreign_customer_payload
    )
    assert customer_response.status_code == status.HTTP_404_NOT_FOUND
    assert customer_response.json()["error"]["code"] == "customer_not_found"


def test_appointment_permissions(client: TestClient, session: Session) -> None:
    owner, tenant, employee, service = _setup(client, session)
    manager = _add_role(client, session, tenant["id"], MembershipRole.MANAGER)
    staff = _add_role(client, session, tenant["id"], MembershipRole.STAFF)
    appointment = _create(client, manager, employee, service)
    assert client.get(
        f"/api/v1/appointments/{appointment['id']}", headers=staff
    ).status_code == status.HTTP_200_OK
    assert client.patch(
        f"/api/v1/appointments/{appointment['id']}",
        headers=staff,
        json={"notes": "Forbidden"},
    ).status_code == status.HTTP_403_FORBIDDEN
    assert client.post(
        f"/api/v1/appointments/{appointment['id']}/cancel",
        headers=owner,
        json={},
    ).status_code == status.HTTP_200_OK
