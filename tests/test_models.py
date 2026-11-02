from datetime import datetime, time, timedelta, timezone

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import (
    Appointment,
    AppointmentService,
    AppointmentStatus,
    Customer,
    Employee,
    EmployeeService,
    Location,
    Membership,
    MembershipRole,
    OpeningHour,
    Service,
    Tenant,
    User,
)


def create_business(session: Session) -> tuple[Tenant, Location, Employee]:
    tenant = Tenant(name="Test Tenant", slug="test-tenant")
    location = Location(name="Brussels", slug="brussels")
    employee = Employee(first_name="Ada", last_name="Lovelace")
    tenant.locations.append(location)
    tenant.employees.append(employee)
    location.employees.append(employee)
    session.add(tenant)
    session.flush()
    return tenant, location, employee


def appointment(
    tenant: Tenant,
    location: Location,
    employee: Employee,
    starts_at: datetime,
    ends_at: datetime,
    status: str = AppointmentStatus.CONFIRMED.value,
) -> Appointment:
    return Appointment(
        tenant_id=tenant.id,
        location_id=location.id,
        employee_id=employee.id,
        starts_at=starts_at,
        ends_at=ends_at,
        status=status,
        customer_name="Grace Hopper",
    )


def test_tenant_with_multiple_locations(session: Session) -> None:
    tenant = Tenant(name="Multi Site", slug="multi-site")
    tenant.locations = [
        Location(name="North", slug="north"),
        Location(name="South", slug="south"),
    ]
    session.add(tenant)
    session.flush()

    assert len(tenant.locations) == 2
    assert all(location.tenant_id == tenant.id for location in tenant.locations)


def test_user_membership_and_tenant_user_uniqueness(session: Session) -> None:
    tenant = Tenant(name="Membership Tenant", slug="membership-tenant")
    user = User(
        email="owner@example.com",
        password_hash="not-a-real-password-hash",
        first_name="Owner",
        last_name="Example",
    )
    membership = Membership(role=MembershipRole.OWNER.value, tenant=tenant, user=user)
    session.add(membership)
    session.flush()

    assert membership in user.memberships
    assert membership in tenant.memberships

    with pytest.raises(IntegrityError), session.begin_nested():
        session.add(Membership(tenant_id=tenant.id, user_id=user.id, role=MembershipRole.STAFF.value))
        session.flush()


def test_employee_without_user_and_employee_service(session: Session) -> None:
    tenant, location, employee = create_business(session)
    service = Service(
        tenant=tenant,
        location=location,
        name="Consultation",
        duration_minutes=30,
        price_cents=5000,
    )
    link = EmployeeService(employee=employee, service=service)
    session.add(link)
    session.flush()

    assert employee.user_id is None
    assert employee.services == [service]
    assert service.employees == [employee]


@pytest.mark.parametrize("duration", [0, -1])
def test_service_duration_must_be_positive(session: Session, duration: int) -> None:
    tenant, location, _ = create_business(session)
    with pytest.raises(IntegrityError), session.begin_nested():
        session.add(Service(tenant=tenant, location=location, name="Invalid", duration_minutes=duration))
        session.flush()


@pytest.mark.parametrize(
    ("starts_at", "ends_at"),
    [(time(9), time(9)), (time(10), time(9))],
)
def test_opening_hour_requires_increasing_times(
    session: Session, starts_at: time, ends_at: time
) -> None:
    tenant, location, _ = create_business(session)
    with pytest.raises(IntegrityError), session.begin_nested():
        session.add(
            OpeningHour(
                tenant=tenant,
                location=location,
                weekday=0,
                starts_at=starts_at,
                ends_at=ends_at,
            )
        )
        session.flush()


def test_customer_without_email(session: Session) -> None:
    tenant = Tenant(name="Customer Tenant", slug="customer-tenant")
    customer = Customer(tenant=tenant, first_name="No", last_name="Email")
    session.add(customer)
    session.flush()

    assert customer.email is None


def test_appointment_with_multiple_service_snapshots(session: Session) -> None:
    tenant, location, employee = create_business(session)
    haircut = Service(tenant=tenant, location=location, name="Haircut", duration_minutes=30)
    color = Service(tenant=tenant, location=location, name="Color", duration_minutes=60)
    starts_at = datetime(2026, 8, 4, 9, tzinfo=timezone.utc)
    booking = appointment(tenant, location, employee, starts_at, starts_at + timedelta(minutes=90))
    booking.services = [
        AppointmentService(service=haircut, service_name="Haircut", duration_minutes=30, position=0),
        AppointmentService(service=color, service_name="Color", duration_minutes=60, price_cents=8000, position=1),
    ]
    session.add(booking)
    session.flush()

    assert [item.service_name for item in booking.services] == ["Haircut", "Color"]


def test_active_appointments_cannot_overlap_for_same_employee(session: Session) -> None:
    tenant, location, employee = create_business(session)
    starts_at = datetime(2026, 8, 5, 10, tzinfo=timezone.utc)
    session.add(appointment(tenant, location, employee, starts_at, starts_at + timedelta(minutes=30)))
    session.flush()

    with pytest.raises(IntegrityError), session.begin_nested():
        session.add(
            appointment(
                tenant,
                location,
                employee,
                starts_at + timedelta(minutes=15),
                starts_at + timedelta(minutes=45),
            )
        )
        session.flush()


def test_consecutive_appointments_are_allowed(session: Session) -> None:
    tenant, location, employee = create_business(session)
    starts_at = datetime(2026, 8, 5, 11, tzinfo=timezone.utc)
    session.add_all(
        [
            appointment(tenant, location, employee, starts_at, starts_at + timedelta(minutes=30)),
            appointment(
                tenant,
                location,
                employee,
                starts_at + timedelta(minutes=30),
                starts_at + timedelta(minutes=60),
            ),
        ]
    )
    session.flush()


def test_simultaneous_appointments_are_allowed_for_different_employees(session: Session) -> None:
    tenant, location, employee = create_business(session)
    other_employee = Employee(
        tenant=tenant, location=location, first_name="Alan", last_name="Turing"
    )
    session.add(other_employee)
    session.flush()
    starts_at = datetime(2026, 8, 5, 12, tzinfo=timezone.utc)
    session.add_all(
        [
            appointment(tenant, location, employee, starts_at, starts_at + timedelta(minutes=30)),
            appointment(tenant, location, other_employee, starts_at, starts_at + timedelta(minutes=30)),
        ]
    )
    session.flush()


def test_active_appointment_can_overlap_cancelled_appointment(session: Session) -> None:
    tenant, location, employee = create_business(session)
    starts_at = datetime(2026, 8, 5, 13, tzinfo=timezone.utc)
    session.add_all(
        [
            appointment(
                tenant,
                location,
                employee,
                starts_at,
                starts_at + timedelta(minutes=30),
                AppointmentStatus.CANCELLED.value,
            ),
            appointment(tenant, location, employee, starts_at, starts_at + timedelta(minutes=30)),
        ]
    )
    session.flush()
