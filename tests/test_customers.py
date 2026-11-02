from uuid import UUID

from fastapi import status
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.customer import Customer
from app.models.membership import Membership, MembershipRole
from app.models.user import User
from tests.support import create_owned_tenant, create_user_headers


PASSWORD = "correct-horse-battery-staple"


def _auth_headers(client: TestClient, email: str) -> dict[str, str]:
    return create_user_headers(
        client, email, first_name="Customer", last_name="Tester"
    )


def _setup_owner(
    client: TestClient,
    *,
    email: str = "customer-owner@example.com",
    slug: str = "customer-tenant",
) -> tuple[dict[str, str], dict[str, object]]:
    auth = _auth_headers(client, email)
    tenant = create_owned_tenant(
        client,
        auth,
        name=slug.replace("-", " ").title(),
        slug=slug,
    )
    return {**auth, "X-Tenant-ID": tenant["id"]}, tenant


def _add_role(
    client: TestClient,
    session: Session,
    tenant_id: str,
    role: MembershipRole,
) -> dict[str, str]:
    email = f"customer-{role.value}@example.com"
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


def _create_customer(
    client: TestClient,
    headers: dict[str, str],
    *,
    first_name: str = "Ada",
    last_name: str = "Lovelace",
    email: str | None = "ada@example.com",
    phone: str | None = "+32123456789",
) -> dict[str, object]:
    response = client.post(
        "/api/v1/customers",
        headers=headers,
        json={
            "first_name": first_name,
            "last_name": last_name,
            "email": email,
            "phone": phone,
            "notes": "Prefers mornings",
            "marketing_consent": True,
        },
    )
    assert response.status_code == status.HTTP_201_CREATED
    return response.json()


def test_customer_crud(client: TestClient) -> None:
    headers, _ = _setup_owner(client)
    customer = _create_customer(client, headers, email="ADA@EXAMPLE.COM")
    assert "tenant_id" not in customer
    assert customer["email"] == "ada@example.com"

    read = client.get(f"/api/v1/customers/{customer['id']}", headers=headers)
    assert read.status_code == status.HTTP_200_OK
    updated = client.patch(
        f"/api/v1/customers/{customer['id']}",
        headers=headers,
        json={"first_name": "Augusta", "marketing_consent": False},
    )
    assert updated.status_code == status.HTTP_200_OK
    assert updated.json()["first_name"] == "Augusta"
    assert updated.json()["marketing_consent"] is False

    deleted = client.delete(f"/api/v1/customers/{customer['id']}", headers=headers)
    assert deleted.status_code == status.HTTP_204_NO_CONTENT
    hidden = client.get(f"/api/v1/customers/{customer['id']}", headers=headers)
    assert hidden.status_code == status.HTTP_404_NOT_FOUND


def test_customer_search_by_query_email_and_phone(client: TestClient) -> None:
    headers, _ = _setup_owner(client)
    ada = _create_customer(client, headers)
    grace = _create_customer(
        client,
        headers,
        first_name="Grace",
        last_name="Hopper",
        email="grace@example.com",
        phone="+32987654321",
    )

    by_name = client.get("/api/v1/customers?query=hopper", headers=headers)
    assert [item["id"] for item in by_name.json()["items"]] == [grace["id"]]
    assert by_name.json()["total"] == 1
    by_partial_email = client.get("/api/v1/customers?query=ada@", headers=headers)
    assert [item["id"] for item in by_partial_email.json()["items"]] == [ada["id"]]
    by_email = client.get(
        "/api/v1/customers?email=GRACE%40EXAMPLE.COM",
        headers=headers,
    )
    assert [item["id"] for item in by_email.json()["items"]] == [grace["id"]]
    by_phone = client.get(
        "/api/v1/customers?phone=%2B32123456789",
        headers=headers,
    )
    assert [item["id"] for item in by_phone.json()["items"]] == [ada["id"]]

    page = client.get("/api/v1/customers?page=2&page_size=1", headers=headers)
    assert page.status_code == status.HTTP_200_OK
    assert page.json()["page"] == 2
    assert page.json()["page_size"] == 1
    assert page.json()["total"] == 2
    assert len(page.json()["items"]) == 1
    assert client.get("/api/v1/customers?page=0", headers=headers).status_code == 422
    assert client.get("/api/v1/customers?page_size=101", headers=headers).status_code == 422


def test_duplicate_email_and_phone_are_allowed(client: TestClient, session: Session) -> None:
    headers, tenant = _setup_owner(client)
    first = _create_customer(client, headers)
    second = _create_customer(
        client,
        headers,
        first_name="Different",
        last_name="Person",
    )
    assert first["email"] == second["email"]
    assert first["phone"] == second["phone"]
    customers = list(
        session.scalars(select(Customer).where(Customer.tenant_id == UUID(tenant["id"])))
    )
    assert len(customers) == 2


def test_customers_are_tenant_scoped(client: TestClient) -> None:
    first_headers, _ = _setup_owner(client)
    first_customer = _create_customer(client, first_headers)
    second_headers, _ = _setup_owner(
        client,
        email="customer-second@example.com",
        slug="customer-second-tenant",
    )
    second_customer = _create_customer(
        client,
        second_headers,
        first_name="Second",
        last_name="Tenant",
    )

    first_list = client.get("/api/v1/customers", headers=first_headers).json()["items"]
    assert [item["id"] for item in first_list] == [first_customer["id"]]
    hidden = client.get(
        f"/api/v1/customers/{second_customer['id']}",
        headers=first_headers,
    )
    assert hidden.status_code == status.HTTP_404_NOT_FOUND
    assert hidden.json()["error"]["code"] == "customer_not_found"
    assert client.patch(
        f"/api/v1/customers/{second_customer['id']}",
        headers=first_headers,
        json={"notes": "cross tenant"},
    ).status_code == status.HTTP_404_NOT_FOUND


def test_customer_permissions(client: TestClient, session: Session) -> None:
    owner_headers, tenant = _setup_owner(client)
    manager = _add_role(client, session, tenant["id"], MembershipRole.MANAGER)
    staff = _add_role(client, session, tenant["id"], MembershipRole.STAFF)
    customer = _create_customer(client, manager)

    assert client.get("/api/v1/customers", headers=staff).status_code == 200
    assert client.post(
        "/api/v1/customers",
        headers=staff,
        json={"first_name": "Read", "last_name": "Only"},
    ).status_code == status.HTTP_403_FORBIDDEN
    assert client.delete(
        f"/api/v1/customers/{customer['id']}", headers=owner_headers
    ).status_code == status.HTTP_204_NO_CONTENT


def test_customer_dto_rejects_tenant_id_and_invalid_email(client: TestClient) -> None:
    headers, tenant = _setup_owner(client)
    tenant_id_response = client.post(
        "/api/v1/customers",
        headers=headers,
        json={
            "tenant_id": tenant["id"],
            "first_name": "Invalid",
            "last_name": "Tenant",
        },
    )
    assert tenant_id_response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
    invalid_email = client.post(
        "/api/v1/customers",
        headers=headers,
        json={
            "first_name": "Invalid",
            "last_name": "Email",
            "email": "not-an-email",
        },
    )
    assert invalid_email.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
