from collections.abc import Generator
import secrets
import hashlib
from urllib.parse import parse_qs, urlparse
from uuid import UUID, uuid4

import psycopg
import pytest
from fastapi import status
from fastapi.testclient import TestClient
from psycopg import sql
from sqlalchemy import Engine, create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from app.core.database import (
    create_application_engine,
    get_database_session,
    set_session_tenant,
)
from app.main import app
from app.core.security import hash_password


@pytest.fixture
def rls_login_url(test_database_url: str) -> Generator[str, None, None]:
    owner_url = make_url(test_database_url)
    login_role = f"bsrm_booking_test_{uuid4().hex}"
    login_password = secrets.token_urlsafe(32)
    admin_url = owner_url.set(drivername="postgresql")
    with psycopg.connect(
        admin_url.render_as_string(hide_password=False),
        autocommit=True,
    ) as connection:
        connection.execute(
            sql.SQL(
                "CREATE ROLE {} LOGIN PASSWORD {} "
                "NOSUPERUSER NOCREATEDB NOCREATEROLE INHERIT NOBYPASSRLS"
            ).format(sql.Identifier(login_role), sql.Literal(login_password))
        )
        connection.execute(
            sql.SQL("GRANT bsrm_booking_app TO {}").format(
                sql.Identifier(login_role)
            )
        )

    try:
        yield owner_url.set(
            username=login_role,
            password=login_password,
        ).render_as_string(hide_password=False)
    finally:
        with psycopg.connect(
            admin_url.render_as_string(hide_password=False),
            autocommit=True,
        ) as connection:
            connection.execute(
                sql.SQL("DROP ROLE IF EXISTS {}").format(
                    sql.Identifier(login_role)
                )
            )


@pytest.fixture
def rls_engine(rls_login_url: str) -> Generator[Engine, None, None]:
    engine = create_application_engine(rls_login_url)
    try:
        yield engine
    finally:
        engine.dispose()


def _seed_tenant_locations(database_url: str) -> tuple[UUID, UUID, UUID, UUID]:
    tenant_a = uuid4()
    tenant_b = uuid4()
    location_a = uuid4()
    location_b = uuid4()
    owner_engine = create_engine(database_url)
    try:
        with owner_engine.begin() as connection:
            connection.execute(
                text(
                    "INSERT INTO tenants (id, name, slug, is_active) VALUES "
                    "(:tenant_a, 'RLS Tenant A', :slug_a, true), "
                    "(:tenant_b, 'RLS Tenant B', :slug_b, true)"
                ),
                {
                    "tenant_a": tenant_a,
                    "tenant_b": tenant_b,
                    "slug_a": f"rls-a-{tenant_a}",
                    "slug_b": f"rls-b-{tenant_b}",
                },
            )
            connection.execute(
                text(
                    "INSERT INTO locations "
                    "(id, tenant_id, name, slug, timezone, is_active) VALUES "
                    "(:location_a, :tenant_a, 'A', 'a', 'UTC', true), "
                    "(:location_b, :tenant_b, 'B', 'b', 'UTC', true)"
                ),
                {
                    "location_a": location_a,
                    "location_b": location_b,
                    "tenant_a": tenant_a,
                    "tenant_b": tenant_b,
                },
            )
    finally:
        owner_engine.dispose()
    return tenant_a, tenant_b, location_a, location_b


def _delete_seeded_tenants(database_url: str, *tenant_ids: UUID) -> None:
    owner_engine = create_engine(database_url)
    try:
        with owner_engine.begin() as connection:
            connection.execute(
                text("DELETE FROM tenants WHERE id = ANY(:tenant_ids)"),
                {"tenant_ids": list(tenant_ids)},
            )
    finally:
        owner_engine.dispose()


def test_application_role_is_non_privileged_and_catalog_policies_exist(
    rls_engine: Engine,
) -> None:
    with rls_engine.connect() as connection:
        runtime = connection.execute(
            text(
                "SELECT session_user, current_user, login.rolsuper, "
                "login.rolbypassrls, effective.rolsuper, effective.rolbypassrls "
                "FROM pg_roles AS login, pg_roles AS effective "
                "WHERE login.rolname = session_user AND effective.rolname = current_user"
            )
        ).one()
        protected = connection.execute(
            text(
                "SELECT relname, relrowsecurity, relforcerowsecurity, "
                "pg_get_userbyid(relowner) AS owner "
                "FROM pg_class WHERE relname = ANY(:tables) ORDER BY relname"
            ),
            {
                "tables": [
                    "locations",
                    "memberships",
                    "employees",
                    "services",
                    "opening_hours",
                    "employee_availabilities",
                    "time_off",
                    "location_closures",
                    "customers",
                    "appointments",
                    "tenant_invitations",
                    "booking_sites",
                    "public_booking_idempotency",
                    "public_booking_rate_limits",
                ]
            },
        ).all()
        policy_count = connection.scalar(
            text(
                "SELECT count(*) FROM pg_policies "
                "WHERE schemaname = 'public' AND policyname LIKE 'tenant_isolation_%'"
            )
        )

    assert runtime[0].startswith("bsrm_booking_test_")
    assert runtime[1:] == ("bsrm_booking_app", False, False, False, False)
    assert len(protected) == 14
    assert all(row.relrowsecurity and row.relforcerowsecurity for row in protected)
    assert all(row.owner != "bsrm_booking_app" for row in protected)
    assert policy_count == 16


def test_rls_blocks_cross_tenant_read_update_and_insert(
    test_database_url: str,
    rls_engine: Engine,
) -> None:
    tenant_a, tenant_b, location_a, location_b = _seed_tenant_locations(test_database_url)
    try:
        with Session(rls_engine) as session:
            assert session.scalar(text("SELECT count(*) FROM locations")) == 0

            set_session_tenant(session, tenant_a)
            assert session.scalars(text("SELECT id FROM locations")).all() == [location_a]

            updated = session.execute(
                text("UPDATE locations SET name = 'forbidden' WHERE id = :location_id"),
                {"location_id": location_b},
            )
            assert updated.rowcount == 0

            with pytest.raises(DBAPIError, match="row-level security policy"):
                session.execute(
                    text(
                        "INSERT INTO locations "
                        "(id, tenant_id, name, slug, timezone, is_active) "
                        "VALUES (:id, :tenant_id, 'Forbidden', 'forbidden', 'UTC', true)"
                    ),
                    {"id": uuid4(), "tenant_id": tenant_b},
                )
                session.flush()
            session.rollback()

            # A new transaction in the same request/session restores tenant A.
            assert session.scalars(text("SELECT id FROM locations")).all() == [location_a]
    finally:
        _delete_seeded_tenants(test_database_url, tenant_a, tenant_b)


def test_public_booking_key_resolution_does_not_bypass_tenant_rls(
    test_database_url: str,
    rls_engine: Engine,
) -> None:
    tenant_a, tenant_b, _, _ = _seed_tenant_locations(test_database_url)
    site_a = uuid4()
    site_b = uuid4()
    raw_key = f"bsrm_pk_test_{secrets.token_urlsafe(32)}"
    key_hash = hashlib.sha256(raw_key.encode("utf-8")).hexdigest()
    owner_engine = create_engine(test_database_url)
    try:
        with owner_engine.begin() as connection:
            connection.execute(
                text(
                    "INSERT INTO booking_sites "
                    "(id, tenant_id, name, publishable_key_hash, key_prefix, allowed_origins) "
                    "VALUES (:site_a, :tenant_a, 'A', :key_hash, 'bsrm_pk_test_a', '{}'), "
                    "(:site_b, :tenant_b, 'B', :other_hash, 'bsrm_pk_test_b', '{}')"
                ),
                {
                    "site_a": site_a,
                    "tenant_a": tenant_a,
                    "key_hash": key_hash,
                    "site_b": site_b,
                    "tenant_b": tenant_b,
                    "other_hash": hashlib.sha256(b"other").hexdigest(),
                },
            )

        with Session(rls_engine) as session:
            assert session.scalar(text("SELECT count(*) FROM booking_sites")) == 0
            resolved = session.execute(
                text(
                    "SELECT id, tenant_id FROM public.app_resolve_booking_site(:key_hash)"
                ),
                {"key_hash": key_hash},
            ).one()
            assert resolved == (site_a, tenant_a)

            set_session_tenant(session, tenant_a)
            assert session.scalars(text("SELECT id FROM booking_sites")).all() == [site_a]
            assert session.scalar(
                text("SELECT count(*) FROM booking_sites WHERE id = :site_b"),
                {"site_b": site_b},
            ) == 0
    finally:
        owner_engine.dispose()
        _delete_seeded_tenants(test_database_url, tenant_a, tenant_b)


def test_transaction_rollback_and_pool_reuse_do_not_leak_tenant(
    test_database_url: str,
    rls_engine: Engine,
) -> None:
    tenant_a, tenant_b, location_a, location_b = _seed_tenant_locations(test_database_url)
    try:
        with rls_engine.connect() as connection:
            first_transaction = connection.begin()
            connection.exec_driver_sql(f"SET LOCAL app.tenant_id = '{tenant_a}'")
            assert connection.scalar(text("SELECT count(*) FROM locations")) == 1
            backend_pid = connection.scalar(text("SELECT pg_backend_pid()"))
            first_transaction.rollback()

            second_transaction = connection.begin()
            assert connection.scalar(
                text("SELECT NULLIF(current_setting('app.tenant_id', true), '')")
            ) is None
            assert connection.scalar(text("SELECT count(*) FROM locations")) == 0
            second_transaction.rollback()

        with Session(rls_engine) as first_session:
            set_session_tenant(first_session, tenant_a)
            first_pid = first_session.scalar(text("SELECT pg_backend_pid()"))
            assert first_session.scalars(text("SELECT id FROM locations")).all() == [location_a]

        with Session(rls_engine) as second_session:
            set_session_tenant(second_session, tenant_b)
            second_pid = second_session.scalar(text("SELECT pg_backend_pid()"))
            assert second_session.scalars(text("SELECT id FROM locations")).all() == [location_b]

        assert first_pid == second_pid == backend_pid
    finally:
        _delete_seeded_tenants(test_database_url, tenant_a, tenant_b)


def test_auth_and_tenant_routes_work_with_real_application_role(
    test_database_url: str,
    rls_engine: Engine,
) -> None:
    platform_email = f"rls-platform-{uuid4()}@example.com"
    invited_email = f"rls-invited-{uuid4()}@example.com"
    platform_user_id = uuid4()
    platform_role_id = uuid4()
    tenant_slugs = [f"rls-app-a-{uuid4()}", f"rls-app-b-{uuid4()}"]

    owner_engine = create_engine(test_database_url)
    try:
        with owner_engine.begin() as connection:
            connection.execute(
                text(
                    "INSERT INTO users "
                    "(id, email, password_hash, first_name, last_name, is_active) "
                    "VALUES (:id, :email, :password_hash, 'Platform', 'Admin', true)"
                ),
                {
                    "id": platform_user_id,
                    "email": platform_email,
                    "password_hash": hash_password("StrongPassword123!"),
                },
            )
            connection.execute(
                text(
                    "INSERT INTO platform_roles (id, user_id, role, is_active) "
                    "VALUES (:id, :user_id, 'platform_admin', true)"
                ),
                {"id": platform_role_id, "user_id": platform_user_id},
            )
    finally:
        owner_engine.dispose()

    def override_session() -> Generator[Session, None, None]:
        with Session(rls_engine, expire_on_commit=False) as session:
            yield session

    app.dependency_overrides[get_database_session] = override_session
    try:
        with TestClient(app, base_url="http://localhost") as client:
            login = client.post(
                "/api/v1/auth/login",
                data={"username": platform_email, "password": "StrongPassword123!"},
            )
            assert login.status_code == status.HTTP_200_OK
            tokens = login.json()
            auth = {"Authorization": f"Bearer {tokens['access_token']}"}
            assert client.get("/api/v1/auth/me", headers=auth).status_code == 200

            refreshed = client.post(
                "/api/v1/auth/refresh",
                json={"refresh_token": tokens["refresh_token"]},
            )
            assert refreshed.status_code == status.HTTP_200_OK
            assert client.post(
                "/api/v1/auth/logout",
                json={"refresh_token": refreshed.json()["refresh_token"]},
            ).status_code == status.HTTP_204_NO_CONTENT

            tenants: list[dict[str, object]] = []
            for index, slug in enumerate(tenant_slugs):
                response = client.post(
                    "/api/v1/platform/tenants",
                    headers=auth,
                    json={"name": f"RLS API Tenant {index}", "slug": slug},
                )
                assert response.status_code == status.HTTP_201_CREATED, response.text
                tenants.append(response.json())

            invitation_tokens: list[str] = []
            for tenant in tenants:
                invitation = client.post(
                    f"/api/v1/platform/tenants/{tenant['id']}/invitations",
                    headers=auth,
                    json={"email": invited_email, "role": "owner"},
                )
                assert invitation.status_code == status.HTTP_201_CREATED
                invitation_tokens.append(
                    parse_qs(urlparse(invitation.json()["acceptance_url"]).query)[
                        "token"
                    ][0]
                )

            accepted = client.post(
                "/api/v1/auth/invitations/accept",
                json={
                    "token": invitation_tokens[0],
                    "password": "InvitedPassword123!",
                    "first_name": "Invited",
                    "last_name": "Owner",
                },
            )
            assert accepted.status_code == status.HTTP_201_CREATED
            invited_login = client.post(
                "/api/v1/auth/login",
                data={"username": invited_email, "password": "InvitedPassword123!"},
            )
            assert invited_login.status_code == status.HTTP_200_OK
            invited_auth = {
                "Authorization": f"Bearer {invited_login.json()['access_token']}"
            }
            second_acceptance = client.post(
                "/api/v1/auth/invitations/accept-existing",
                headers=invited_auth,
                json={"token": invitation_tokens[1]},
            )
            assert second_acceptance.status_code == status.HTTP_200_OK

            tenant_b_headers = {
                **invited_auth,
                "X-Tenant-ID": str(tenants[1]["id"]),
            }
            location_b = client.post(
                f"/api/v1/tenants/{tenants[1]['id']}/locations",
                headers=tenant_b_headers,
                json={"name": "Tenant B Location", "slug": "tenant-b", "timezone": "UTC"},
            )
            assert location_b.status_code == status.HTTP_201_CREATED

            hidden = client.get(
                f"/api/v1/tenants/{tenants[0]['id']}/locations/{location_b.json()['id']}",
                headers=invited_auth,
            )
            assert hidden.status_code == status.HTTP_404_NOT_FOUND
            assert client.get("/health").status_code == 200
            assert client.get("/ready").status_code == 200
            assert client.get("/docs").status_code == 200
    finally:
        app.dependency_overrides.pop(get_database_session, None)
        owner_engine = create_engine(test_database_url)
        try:
            with owner_engine.begin() as connection:
                connection.execute(
                    text("DELETE FROM tenants WHERE slug = ANY(:slugs)"),
                    {"slugs": tenant_slugs},
                )
                connection.execute(
                    text("DELETE FROM users WHERE email = ANY(:emails)"),
                    {"emails": [platform_email, invited_email]},
                )
        finally:
            owner_engine.dispose()
