from datetime import datetime, time, timezone
from uuid import UUID

import pytest
from fastapi import status
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.location import Location
from app.models.location_closure import LocationClosure
from app.models.membership import Membership, MembershipRole
from app.models.opening_hour import OpeningHour
from app.models.tenant import Tenant
from app.models.user import User
from tests.support import create_owned_tenant, create_user_headers


PASSWORD = "correct-horse-battery-staple"


def _auth_headers(client: TestClient, email: str) -> dict[str, str]:
    return create_user_headers(
        client, email, first_name="Hours", last_name="Tester"
    )


def _setup_owner(
    client: TestClient,
    *,
    email: str = "hours-owner@example.com",
    slug: str = "hours-tenant",
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
    return {**auth, "X-Tenant-ID": tenant["id"]}, tenant, location_response.json()


def _add_role(
    client: TestClient,
    session: Session,
    tenant_id: str,
    role: MembershipRole,
) -> dict[str, str]:
    email = f"hours-{role.value}@example.com"
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


def test_opening_hours_allow_multiple_ranges_and_soft_deactivation(
    client: TestClient,
) -> None:
    headers, _, location = _setup_owner(client)
    base_url = f"/api/v1/locations/{location['id']}/opening-hours"

    morning = client.post(
        base_url,
        headers=headers,
        json={"weekday": 1, "starts_at": "09:00", "ends_at": "12:00"},
    )
    afternoon = client.post(
        base_url,
        headers=headers,
        json={"weekday": 1, "starts_at": "13:00", "ends_at": "18:00"},
    )
    assert morning.status_code == status.HTTP_201_CREATED
    assert afternoon.status_code == status.HTTP_201_CREATED
    assert len(client.get(base_url, headers=headers).json()) == 2

    patched = client.patch(
        f"{base_url}/{morning.json()['id']}",
        headers=headers,
        json={"starts_at": "08:30"},
    )
    assert patched.status_code == status.HTTP_200_OK
    assert patched.json()["starts_at"] == "08:30:00"

    deleted = client.delete(
        f"{base_url}/{morning.json()['id']}",
        headers=headers,
    )
    assert deleted.status_code == status.HTTP_200_OK
    assert deleted.json()["is_active"] is False
    assert len(client.get(base_url, headers=headers).json()) == 1
    assert len(client.get(f"{base_url}?is_active=false", headers=headers).json()) == 1


@pytest.mark.parametrize(
    "payload",
    [
        {"weekday": -1, "starts_at": "09:00", "ends_at": "10:00"},
        {"weekday": 7, "starts_at": "09:00", "ends_at": "10:00"},
        {"weekday": 1, "starts_at": "10:00", "ends_at": "10:00"},
        {"weekday": 1, "starts_at": "11:00", "ends_at": "10:00"},
    ],
)
def test_opening_hour_dto_rejects_invalid_ranges(
    client: TestClient,
    payload: dict[str, object],
) -> None:
    headers, _, location = _setup_owner(client)
    response = client.post(
        f"/api/v1/locations/{location['id']}/opening-hours",
        headers=headers,
        json=payload,
    )
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT


def test_opening_hour_partial_update_revalidates_persisted_range(
    client: TestClient,
) -> None:
    headers, _, location = _setup_owner(client)
    base_url = f"/api/v1/locations/{location['id']}/opening-hours"
    created = client.post(
        base_url,
        headers=headers,
        json={"weekday": 2, "starts_at": "09:00", "ends_at": "17:00"},
    ).json()
    response = client.patch(
        f"{base_url}/{created['id']}",
        headers=headers,
        json={"starts_at": "18:00"},
    )
    assert response.status_code == status.HTTP_400_BAD_REQUEST


def test_location_closure_crud_and_temporal_validation(client: TestClient) -> None:
    headers, _, location = _setup_owner(client)
    base_url = f"/api/v1/locations/{location['id']}/closures"
    created = client.post(
        base_url,
        headers=headers,
        json={
            "starts_at": "2026-12-24T12:00:00+01:00",
            "ends_at": "2026-12-26T09:00:00+01:00",
            "reason": "Holiday",
        },
    )
    assert created.status_code == status.HTTP_201_CREATED
    closure = created.json()
    assert "tenant_id" not in closure
    assert client.get(f"{base_url}/{closure['id']}", headers=headers).status_code == 200

    patched = client.patch(
        f"{base_url}/{closure['id']}",
        headers=headers,
        json={"reason": "Winter holiday"},
    )
    assert patched.status_code == status.HTTP_200_OK
    assert patched.json()["reason"] == "Winter holiday"
    assert len(client.get(base_url, headers=headers).json()) == 1

    invalid = client.post(
        base_url,
        headers=headers,
        json={
            "starts_at": "2026-12-24T12:00:00+01:00",
            "ends_at": "2026-12-24T11:00:00+01:00",
        },
    )
    assert invalid.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
    naive_patch = client.patch(
        f"{base_url}/{closure['id']}",
        headers=headers,
        json={"starts_at": "2026-12-24T13:00:00"},
    )
    assert naive_patch.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT

    deleted = client.delete(f"{base_url}/{closure['id']}", headers=headers)
    assert deleted.status_code == status.HTTP_204_NO_CONTENT
    assert client.get(f"{base_url}/{closure['id']}", headers=headers).status_code == 404


def test_hours_are_tenant_scoped(client: TestClient) -> None:
    first_headers, _, first_location = _setup_owner(client)
    second_headers, _, second_location = _setup_owner(
        client,
        email="hours-second@example.com",
        slug="hours-second-tenant",
    )
    second_hour = client.post(
        f"/api/v1/locations/{second_location['id']}/opening-hours",
        headers=second_headers,
        json={"weekday": 3, "starts_at": "09:00", "ends_at": "17:00"},
    ).json()

    foreign_location = client.get(
        f"/api/v1/locations/{second_location['id']}/opening-hours",
        headers=first_headers,
    )
    assert foreign_location.status_code == status.HTTP_404_NOT_FOUND
    hidden_hour = client.get(
        f"/api/v1/locations/{first_location['id']}/opening-hours/{second_hour['id']}",
        headers=first_headers,
    )
    assert hidden_hour.status_code == status.HTTP_404_NOT_FOUND


def test_hours_permissions(client: TestClient, session: Session) -> None:
    owner_headers, tenant, location = _setup_owner(client)
    manager_headers = _add_role(client, session, tenant["id"], MembershipRole.MANAGER)
    staff_headers = _add_role(client, session, tenant["id"], MembershipRole.STAFF)
    url = f"/api/v1/locations/{location['id']}/opening-hours"

    created = client.post(
        url,
        headers=manager_headers,
        json={"weekday": 4, "starts_at": "09:00", "ends_at": "17:00"},
    )
    assert created.status_code == status.HTTP_201_CREATED
    assert client.get(url, headers=staff_headers).status_code == status.HTTP_200_OK
    assert client.post(
        url,
        headers=staff_headers,
        json={"weekday": 5, "starts_at": "09:00", "ends_at": "17:00"},
    ).status_code == status.HTTP_403_FORBIDDEN
    assert client.delete(
        f"{url}/{created.json()['id']}", headers=owner_headers
    ).status_code == status.HTTP_200_OK


def test_phase_7_sql_constraints(session: Session) -> None:
    tenant = Tenant(name="Hours SQL", slug="hours-sql")
    location = Location(name="Main", slug="main", tenant=tenant)
    session.add(location)
    session.flush()

    invalid_records = [
        OpeningHour(
            tenant_id=tenant.id,
            location_id=location.id,
            weekday=7,
            starts_at=time(9),
            ends_at=time(10),
        ),
        OpeningHour(
            tenant_id=tenant.id,
            location_id=location.id,
            weekday=1,
            starts_at=time(10),
            ends_at=time(9),
        ),
        LocationClosure(
            tenant_id=tenant.id,
            location_id=location.id,
            starts_at=datetime(2026, 1, 2, tzinfo=timezone.utc),
            ends_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        ),
    ]
    for record in invalid_records:
        with pytest.raises(IntegrityError), session.begin_nested():
            session.add(record)
            session.flush()
