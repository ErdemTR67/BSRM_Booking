from datetime import datetime, time, timedelta
from uuid import uuid4
from zoneinfo import ZoneInfo

from fastapi import status
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.appointment import Appointment
from app.models.employee import Employee
from app.models.employee_availability import EmployeeAvailability
from app.models.employee_service import EmployeeService
from app.models.location import Location
from app.models.membership import MembershipRole
from app.models.opening_hour import OpeningHour
from app.models.service import Service
from app.api.routes.public_booking import get_public_booking_service
from app.core.config import get_settings
from app.core.exceptions import PublicBookingChallengeError
from app.core.turnstile import TurnstileVerifier
from app.main import app
from app.services.public_booking import PublicBookingService
from tests.support import add_membership, create_owned_tenant, create_user_headers


ORIGIN = "http://booking.example.test"
BRUSSELS = ZoneInfo("Europe/Brussels")


def _configured_tenant(client: TestClient, session: Session, suffix: str) -> dict[str, object]:
    headers = create_user_headers(client, f"owner-{suffix}@example.com")
    tenant = create_owned_tenant(
        client,
        headers,
        name=f"Salon {suffix}",
        slug=f"salon-{suffix}-{uuid4().hex[:8]}",
    )
    tenant_id = tenant["id"]
    target_date = datetime.now(BRUSSELS).date() + timedelta(days=1)
    location = Location(
        tenant_id=tenant_id,
        name="Bruxelles",
        slug="bruxelles",
        timezone="Europe/Brussels",
        city="Bruxelles",
        country_code="BE",
    )
    employee = Employee(
        tenant_id=tenant_id,
        location=location,
        first_name="Ada",
        last_name="Lovelace",
        email="private-employee@example.com",
        phone="+32000000000",
        is_active=True,
        is_bookable=True,
    )
    service = Service(
        tenant_id=tenant_id,
        name="Consultation",
        description="Rendez-vous de découverte",
        duration_minutes=30,
        price_cents=5000,
        currency="EUR",
        is_active=True,
    )
    session.add_all([location, employee, service])
    session.flush()
    session.add_all(
        [
            EmployeeService(
                employee_id=employee.id,
                service_id=service.id,
                custom_duration_minutes=45,
                custom_price_cents=4200,
                is_active=True,
            ),
            OpeningHour(
                tenant_id=tenant_id,
                location_id=location.id,
                weekday=target_date.weekday(),
                starts_at=time(9),
                ends_at=time(17),
                is_active=True,
            ),
            EmployeeAvailability(
                tenant_id=tenant_id,
                employee_id=employee.id,
                weekday=target_date.weekday(),
                starts_at=time(9),
                ends_at=time(17),
                valid_from=target_date,
                valid_until=target_date,
                is_active=True,
            ),
        ]
    )
    session.commit()
    site = client.post(
        "/api/v1/booking-site",
        headers={**headers, "X-Tenant-ID": str(tenant_id)},
        json={
            "name": "Site vitrine",
            "allowed_origins": [ORIGIN + "/"],
            "default_location_id": str(location.id),
            "slot_interval_minutes": 15,
            "minimum_notice_minutes": 0,
            "maximum_advance_days": 90,
        },
    )
    assert site.status_code == status.HTTP_201_CREATED, site.text
    return {
        "headers": headers,
        "tenant_id": str(tenant_id),
        "location_id": str(location.id),
        "employee_id": str(employee.id),
        "service_id": str(service.id),
        "target_date": target_date,
        "site_key": site.json()["publishable_key"],
    }


def _public_headers(data: dict[str, object]) -> dict[str, str]:
    return {"X-BSRM-Site-Key": str(data["site_key"]), "Origin": ORIGIN}


def test_booking_site_key_is_returned_once_and_admin_scoped(
    client: TestClient, session: Session
) -> None:
    data = _configured_tenant(client, session, "site")
    private_headers = {
        **data["headers"],
        "X-Tenant-ID": data["tenant_id"],
    }
    fetched = client.get("/api/v1/booking-site", headers=private_headers)
    assert fetched.status_code == status.HTTP_200_OK
    assert "publishable_key" not in fetched.json()
    assert fetched.json()["key_prefix"].startswith("bsrm_pk_test_")

    staff_email = f"staff-{uuid4().hex[:8]}@example.com"
    staff_headers = create_user_headers(client, staff_email)
    add_membership(
        client,
        tenant_id=str(data["tenant_id"]),
        email=staff_email,
        role=MembershipRole.STAFF,
    )
    denied = client.get(
        "/api/v1/booking-site",
        headers={**staff_headers, "X-Tenant-ID": str(data["tenant_id"])},
    )
    assert denied.status_code == status.HTTP_403_FORBIDDEN

    old_key = data["site_key"]
    rotated = client.post("/api/v1/booking-site/rotate-key", headers=private_headers)
    assert rotated.status_code == status.HTTP_200_OK
    assert rotated.json()["publishable_key"] != old_key
    assert client.get(
        "/api/v1/public/booking/context",
        headers={"X-BSRM-Site-Key": str(old_key), "Origin": ORIGIN},
    ).status_code == status.HTTP_404_NOT_FOUND
    assert client.get(
        "/api/v1/public/booking/context",
        headers={
            "X-BSRM-Site-Key": rotated.json()["publishable_key"],
            "Origin": ORIGIN,
        },
    ).status_code == status.HTTP_200_OK

    deactivated = client.delete("/api/v1/booking-site", headers=private_headers)
    assert deactivated.status_code == status.HTTP_200_OK
    assert client.get(
        "/api/v1/public/booking/context",
        headers={
            "X-BSRM-Site-Key": rotated.json()["publishable_key"],
            "Origin": ORIGIN,
        },
    ).status_code == status.HTTP_404_NOT_FOUND


def test_public_catalogue_is_origin_bound_and_does_not_expose_employee_contact(
    client: TestClient, session: Session
) -> None:
    data = _configured_tenant(client, session, "catalogue")
    headers = _public_headers(data)

    missing_key = client.get("/api/v1/public/booking/context", headers={"Origin": ORIGIN})
    assert missing_key.status_code == status.HTTP_404_NOT_FOUND
    assert "www-authenticate" not in missing_key.headers

    wrong_origin = client.get(
        "/api/v1/public/booking/context",
        headers={"X-BSRM-Site-Key": str(data["site_key"]), "Origin": "https://evil.test"},
    )
    assert wrong_origin.status_code == status.HTTP_403_FORBIDDEN

    context = client.get("/api/v1/public/booking/context", headers=headers)
    locations = client.get("/api/v1/public/booking/locations", headers=headers)
    services = client.get(
        "/api/v1/public/booking/services",
        headers=headers,
        params={"location_id": data["location_id"]},
    )
    employees = client.get(
        "/api/v1/public/booking/employees",
        headers=headers,
        params={"location_id": data["location_id"], "service_id": data["service_id"]},
    )
    assert context.status_code == locations.status_code == services.status_code == employees.status_code == 200
    assert context.json()["business"]["name"] == "Salon catalogue"
    assert services.json()[0]["price_cents"] == 5000
    assert set(employees.json()[0]) == {"id", "display_name", "display_color"}


def test_public_booking_is_idempotent_and_tenant_scoped(
    client: TestClient, session: Session
) -> None:
    first = _configured_tenant(client, session, "first")
    second = _configured_tenant(client, session, "second")
    headers = _public_headers(first)

    foreign = client.get(
        "/api/v1/public/booking/services",
        headers=headers,
        params={"location_id": second["location_id"]},
    )
    assert foreign.status_code == status.HTTP_404_NOT_FOUND

    availability = client.get(
        "/api/v1/public/booking/availability",
        headers=headers,
        params={
            "location_id": first["location_id"],
            "service_id": first["service_id"],
            "employee_id": first["employee_id"],
            "date": first["target_date"].isoformat(),
        },
    )
    assert availability.status_code == status.HTTP_200_OK, availability.text
    assert availability.json()
    assert availability.json()[0]["duration_minutes"] == 45
    assert availability.json()[0]["total_duration_minutes"] == 45
    assert availability.json()[0]["price_cents"] == 4200
    starts_at = availability.json()[0]["starts_at"]
    payload = {
        "location_id": first["location_id"],
        "service_id": first["service_id"],
        "employee_id": first["employee_id"],
        "starts_at": starts_at,
        "customer": {
            "first_name": "Grace",
            "last_name": "Hopper",
            "email": "grace@example.com",
        },
    }
    unoffered = {
        **payload,
        "starts_at": (
            datetime.fromisoformat(starts_at) + timedelta(minutes=1)
        ).isoformat(),
    }
    rejected = client.post(
        "/api/v1/public/booking/appointments",
        headers={**headers, "Idempotency-Key": str(uuid4())},
        json=unoffered,
    )
    assert rejected.status_code == status.HTTP_409_CONFLICT

    idem = str(uuid4())
    create_headers = {**headers, "Idempotency-Key": idem}
    created = client.post(
        "/api/v1/public/booking/appointments", headers=create_headers, json=payload
    )
    replay = client.post(
        "/api/v1/public/booking/appointments", headers=create_headers, json=payload
    )
    assert created.status_code == status.HTTP_201_CREATED, created.text
    assert replay.status_code == status.HTTP_200_OK, replay.text
    assert created.json()["starts_at"].endswith("+02:00")
    assert replay.json()["booking_reference"] == created.json()["booking_reference"]
    count = session.scalar(
        select(func.count()).select_from(Appointment).where(
            Appointment.public_reference == created.json()["booking_reference"]
        )
    )
    assert count == 1

    changed = {**payload, "customer_note": "different request"}
    conflict = client.post(
        "/api/v1/public/booking/appointments", headers=create_headers, json=changed
    )
    assert conflict.status_code == status.HTTP_409_CONFLICT
    assert conflict.json()["error"]["code"] == "idempotency_conflict"


def test_public_booking_preflight(client: TestClient) -> None:
    response = client.options(
        "/api/v1/public/booking/appointments",
        headers={
            "Origin": ORIGIN,
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "x-bsrm-site-key,idempotency-key",
        },
    )
    assert response.status_code == status.HTTP_204_NO_CONTENT
    assert response.headers["access-control-allow-origin"] == ORIGIN
    assert "Idempotency-Key" in response.headers["access-control-allow-headers"]

    untrusted = client.options(
        "/api/v1/public/booking/appointments",
        headers={
            "Host": "untrusted.example",
            "Origin": ORIGIN,
            "Access-Control-Request-Method": "POST",
        },
    )
    assert untrusted.status_code == status.HTTP_400_BAD_REQUEST
    assert "access-control-allow-origin" not in untrusted.headers

    oversized = client.post(
        "/api/v1/public/booking/appointments",
        headers={"Origin": ORIGIN, "Content-Type": "application/json"},
        content='{"junk":"' + ("x" * 17_000) + '"}',
    )
    assert oversized.status_code == status.HTTP_413_CONTENT_TOO_LARGE
    assert oversized.json()["error"]["code"] == "request_too_large"


def test_turnstile_mode_rejects_missing_challenge() -> None:
    settings = get_settings().model_copy(
        update={
            "public_booking_challenge_mode": "turnstile",
            "turnstile_secret_key": get_settings().jwt_secret_key,
        }
    )
    verifier = TurnstileVerifier(settings)
    try:
        verifier.verify(
            None,
            remote_ip="127.0.0.1",
            idempotency_key=uuid4(),
            allowed_hostnames={"booking.example.test"},
        )
    except PublicBookingChallengeError:
        pass
    else:
        raise AssertionError("A missing Turnstile token must be rejected.")


def test_turnstile_validates_hostname_and_action(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    settings = get_settings().model_copy(
        update={
            "public_booking_challenge_mode": "turnstile",
            "turnstile_secret_key": get_settings().jwt_secret_key,
            "turnstile_expected_action": "booking",
        }
    )

    class FakeResponse:
        def __enter__(self) -> "FakeResponse":
            return self

        def __exit__(self, *args: object) -> None:
            return None

        def read(self) -> bytes:
            return b'{"success":true,"hostname":"evil.example","action":"booking"}'

    monkeypatch.setattr("app.core.turnstile.urlopen", lambda *args, **kwargs: FakeResponse())
    verifier = TurnstileVerifier(settings)
    try:
        verifier.verify(
            "valid-looking-token",
            remote_ip="127.0.0.1",
            idempotency_key=uuid4(),
            allowed_hostnames={"booking.example.test"},
        )
    except PublicBookingChallengeError:
        pass
    else:
        raise AssertionError("A token issued for another hostname must be rejected.")


def test_public_booking_create_rate_limit(client: TestClient, session: Session) -> None:
    data = _configured_tenant(client, session, "rate")
    headers = _public_headers(data)
    availability = client.get(
        "/api/v1/public/booking/availability",
        headers=headers,
        params={
            "location_id": data["location_id"],
            "service_id": data["service_id"],
            "employee_id": data["employee_id"],
            "date": data["target_date"].isoformat(),
        },
    ).json()
    limited_settings = get_settings().model_copy(
        update={"public_booking_create_rate_limit": 1}
    )
    app.dependency_overrides[get_public_booking_service] = lambda: PublicBookingService(
        session, settings=limited_settings
    )
    try:
        def payload(slot: dict[str, object], email: str) -> dict[str, object]:
            return {
                "location_id": data["location_id"],
                "service_id": data["service_id"],
                "employee_id": data["employee_id"],
                "starts_at": slot["starts_at"],
                "customer": {
                    "first_name": "Rate",
                    "last_name": "Test",
                    "email": email,
                },
            }

        first = client.post(
            "/api/v1/public/booking/appointments",
            headers={**headers, "Idempotency-Key": str(uuid4())},
            json=payload(availability[0], "rate-one@example.com"),
        )
        limited = client.post(
            "/api/v1/public/booking/appointments",
            headers={**headers, "Idempotency-Key": str(uuid4())},
            json=payload(availability[1], "rate-two@example.com"),
        )
    finally:
        app.dependency_overrides.pop(get_public_booking_service, None)

    assert first.status_code == status.HTTP_201_CREATED
    assert limited.status_code == status.HTTP_429_TOO_MANY_REQUESTS
    assert limited.json()["error"]["code"] == "rate_limit_exceeded"
    assert int(limited.headers["retry-after"]) > 0
