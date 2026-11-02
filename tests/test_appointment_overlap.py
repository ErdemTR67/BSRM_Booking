from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from threading import Barrier
from uuid import uuid4
from zoneinfo import ZoneInfo

import pytest
from fastapi import status
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.appointment import Appointment, AppointmentStatus
from app.models.customer import Customer
from app.models.employee import Employee
from app.models.location import Location
from app.models.tenant import Tenant
from app.services.availability import AvailabilityService

from test_appointments import _create, _payload, _setup


TZ = ZoneInfo("Europe/Brussels")


def _appointment(
    employee: Employee,
    *,
    starts_at: datetime,
    ends_at: datetime,
    status_value: AppointmentStatus = AppointmentStatus.PENDING,
) -> Appointment:
    return Appointment(
        tenant_id=employee.tenant_id,
        location_id=employee.location_id,
        employee_id=employee.id,
        starts_at=starts_at,
        ends_at=ends_at,
        status=status_value.value,
        customer_name="Constraint Test",
    )


def test_overlap_constraint_same_employee_and_consecutive_allowed(
    session: Session,
) -> None:
    tenant = Tenant(name="Overlap SQL", slug=f"overlap-sql-{uuid4()}")
    location = Location(name="Main", slug="main", tenant=tenant)
    first_employee = Employee(
        tenant=tenant,
        location=location,
        first_name="First",
        last_name="Employee",
    )
    second_employee = Employee(
        tenant=tenant,
        location=location,
        first_name="Second",
        last_name="Employee",
    )
    session.add_all([first_employee, second_employee])
    session.flush()
    session.add(
        _appointment(
            first_employee,
            starts_at=datetime(2026, 9, 1, 9, tzinfo=TZ),
            ends_at=datetime(2026, 9, 1, 10, tzinfo=TZ),
        )
    )
    session.flush()

    with pytest.raises(IntegrityError), session.begin_nested():
        session.add(
            _appointment(
                first_employee,
                starts_at=datetime(2026, 9, 1, 9, 30, tzinfo=TZ),
                ends_at=datetime(2026, 9, 1, 10, 30, tzinfo=TZ),
            )
        )
        session.flush()

    session.add_all(
        [
            _appointment(
                first_employee,
                starts_at=datetime(2026, 9, 1, 10, tzinfo=TZ),
                ends_at=datetime(2026, 9, 1, 11, tzinfo=TZ),
            ),
            _appointment(
                second_employee,
                starts_at=datetime(2026, 9, 1, 9, tzinfo=TZ),
                ends_at=datetime(2026, 9, 1, 10, tzinfo=TZ),
            ),
            _appointment(
                first_employee,
                starts_at=datetime(2026, 9, 1, 9, 15, tzinfo=TZ),
                ends_at=datetime(2026, 9, 1, 9, 45, tzinfo=TZ),
                status_value=AppointmentStatus.CANCELLED,
            ),
        ]
    )
    session.flush()


def test_exclusion_violation_is_mapped_to_conflict(
    client: TestClient,
    session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    headers, _, employee, service = _setup(
        client,
        session,
        email="appointment-constraint-map@example.com",
        slug="appointment-constraint-map",
    )
    _create(client, headers, employee, service)
    customer_count = session.scalar(select(func.count()).select_from(Customer))
    monkeypatch.setattr(
        AvailabilityService,
        "is_employee_interval_available",
        lambda *args, **kwargs: True,
    )
    response = client.post(
        "/api/v1/appointments",
        headers=headers,
        json=_payload(employee, service, hour=9, minute=15),
    )
    assert response.status_code == status.HTTP_409_CONFLICT
    assert response.json() == {
        "error": {
            "code": "appointment_conflict",
            "message": "The requested appointment time is not available.",
        }
    }
    assert session.scalar(select(func.count()).select_from(Customer)) == customer_count


def test_concurrent_overlapping_inserts_allow_only_one(
    test_database_url: str,
) -> None:
    engine = create_engine(test_database_url)
    tenant_id = None
    try:
        with Session(engine) as setup_session:
            tenant = Tenant(name="Concurrent Overlap", slug=f"concurrent-{uuid4()}")
            location = Location(name="Main", slug="main", tenant=tenant)
            employee = Employee(
                tenant=tenant,
                location=location,
                first_name="Concurrent",
                last_name="Employee",
            )
            setup_session.add(employee)
            setup_session.commit()
            tenant_id = tenant.id
            location_id = location.id
            employee_id = employee.id

        barrier = Barrier(2)

        def insert_appointment(label: str) -> str:
            with Session(engine) as worker_session:
                worker_session.add(
                    Appointment(
                        tenant_id=tenant_id,
                        location_id=location_id,
                        employee_id=employee_id,
                        starts_at=datetime(2026, 10, 1, 9, tzinfo=TZ),
                        ends_at=datetime(2026, 10, 1, 10, tzinfo=TZ),
                        status=AppointmentStatus.PENDING.value,
                        customer_name=label,
                    )
                )
                barrier.wait(timeout=10)
                try:
                    worker_session.commit()
                    return "created"
                except IntegrityError as error:
                    worker_session.rollback()
                    return getattr(error.orig.diag, "constraint_name", "integrity_error")

        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(insert_appointment, ["First", "Second"]))

        assert sorted(results) == [
            "created",
            "excl_appointments_employee_time_overlap",
        ]
    finally:
        if tenant_id is not None:
            with Session(engine) as cleanup_session:
                tenant = cleanup_session.get(Tenant, tenant_id)
                if tenant is not None:
                    cleanup_session.delete(tenant)
                    cleanup_session.commit()
        engine.dispose()
