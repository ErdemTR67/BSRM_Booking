"""enable tenant row level security

Revision ID: c4a91e8d7f20
Revises: b13f6d9132a8
Create Date: 2026-08-11

"""
from typing import Sequence, Union

from alembic import op


revision: str = "c4a91e8d7f20"
down_revision: Union[str, Sequence[str], None] = "b13f6d9132a8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


APPLICATION_ROLE = "bsrm_booking_app"
DIRECT_TENANT_TABLES = (
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
)


def _tenant_expression(column: str = "tenant_id") -> str:
    return (
        f"{column} = NULLIF(current_setting('app.tenant_id', true), '')::uuid"
    )


def upgrade() -> None:
    op.execute(
        f"""
        DO $role$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '{APPLICATION_ROLE}') THEN
                CREATE ROLE {APPLICATION_ROLE}
                    NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOBYPASSRLS;
            ELSE
                ALTER ROLE {APPLICATION_ROLE}
                    NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOBYPASSRLS;
            END IF;
        END
        $role$;

        GRANT USAGE ON SCHEMA public TO {APPLICATION_ROLE};
        GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public
            TO {APPLICATION_ROLE};
        GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO {APPLICATION_ROLE};
        ALTER DEFAULT PRIVILEGES IN SCHEMA public
            GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO {APPLICATION_ROLE};
        ALTER DEFAULT PRIVILEGES IN SCHEMA public
            GRANT USAGE, SELECT ON SEQUENCES TO {APPLICATION_ROLE};
        """
    )

    op.execute(
        """
        CREATE FUNCTION public.app_get_active_membership(
            p_tenant_id uuid,
            p_user_id uuid
        ) RETURNS SETOF public.memberships
        LANGUAGE sql
        STABLE
        SECURITY DEFINER
        SET search_path = pg_catalog, public
        AS $function$
            SELECT membership.*
            FROM public.memberships AS membership
            JOIN public.tenants AS tenant ON tenant.id = membership.tenant_id
            WHERE membership.tenant_id = p_tenant_id
              AND membership.user_id = p_user_id
              AND p_user_id = NULLIF(current_setting('app.user_id', true), '')::uuid
              AND membership.is_active IS TRUE
              AND tenant.is_active IS TRUE
        $function$;

        CREATE FUNCTION public.app_list_active_memberships(
            p_user_id uuid
        ) RETURNS SETOF public.memberships
        LANGUAGE sql
        STABLE
        SECURITY DEFINER
        SET search_path = pg_catalog, public
        AS $function$
            SELECT membership.*
            FROM public.memberships AS membership
            JOIN public.tenants AS tenant ON tenant.id = membership.tenant_id
            WHERE membership.user_id = p_user_id
              AND p_user_id = NULLIF(current_setting('app.user_id', true), '')::uuid
              AND membership.is_active IS TRUE
              AND tenant.is_active IS TRUE
            ORDER BY tenant.name ASC
        $function$;

        CREATE FUNCTION public.app_list_active_tenants(
            p_user_id uuid
        ) RETURNS SETOF public.tenants
        LANGUAGE sql
        STABLE
        SECURITY DEFINER
        SET search_path = pg_catalog, public
        AS $function$
            SELECT tenant.*
            FROM public.tenants AS tenant
            JOIN public.memberships AS membership ON membership.tenant_id = tenant.id
            WHERE membership.user_id = p_user_id
              AND p_user_id = NULLIF(current_setting('app.user_id', true), '')::uuid
              AND membership.is_active IS TRUE
              AND tenant.is_active IS TRUE
            ORDER BY tenant.name ASC
        $function$;

        CREATE FUNCTION public.app_create_tenant_with_owner(
            p_tenant_id uuid,
            p_name text,
            p_slug text,
            p_owner_user_id uuid,
            p_membership_id uuid
        ) RETURNS public.tenants
        LANGUAGE plpgsql
        VOLATILE
        SECURITY DEFINER
        SET search_path = pg_catalog, public
        AS $function$
        DECLARE
            created_tenant public.tenants;
        BEGIN
            IF p_owner_user_id IS DISTINCT FROM
               NULLIF(current_setting('app.user_id', true), '')::uuid THEN
                RAISE EXCEPTION 'Authenticated user context is required'
                    USING ERRCODE = '42501';
            END IF;

            INSERT INTO public.tenants (id, name, slug, is_active)
            VALUES (p_tenant_id, p_name, p_slug, TRUE)
            RETURNING * INTO created_tenant;

            INSERT INTO public.memberships (
                id, tenant_id, user_id, role, is_active
            ) VALUES (
                p_membership_id, p_tenant_id, p_owner_user_id, 'owner', TRUE
            );

            RETURN created_tenant;
        END
        $function$;

        REVOKE ALL ON FUNCTION public.app_get_active_membership(uuid, uuid) FROM PUBLIC;
        REVOKE ALL ON FUNCTION public.app_list_active_memberships(uuid) FROM PUBLIC;
        REVOKE ALL ON FUNCTION public.app_list_active_tenants(uuid) FROM PUBLIC;
        REVOKE ALL ON FUNCTION public.app_create_tenant_with_owner(
            uuid, text, text, uuid, uuid
        ) FROM PUBLIC;

        GRANT EXECUTE ON FUNCTION public.app_get_active_membership(uuid, uuid)
            TO bsrm_booking_app;
        GRANT EXECUTE ON FUNCTION public.app_list_active_memberships(uuid)
            TO bsrm_booking_app;
        GRANT EXECUTE ON FUNCTION public.app_list_active_tenants(uuid)
            TO bsrm_booking_app;
        GRANT EXECUTE ON FUNCTION public.app_create_tenant_with_owner(
            uuid, text, text, uuid, uuid
        ) TO bsrm_booking_app;
        """
    )

    op.execute(
        f"""
        ALTER TABLE tenants ENABLE ROW LEVEL SECURITY;
        ALTER TABLE tenants FORCE ROW LEVEL SECURITY;
        CREATE POLICY tenant_isolation_tenants ON tenants
            TO {APPLICATION_ROLE}
            USING ({_tenant_expression('id')})
            WITH CHECK ({_tenant_expression('id')});
        """
    )

    for table in DIRECT_TENANT_TABLES:
        op.execute(
            f"""
            ALTER TABLE {table} ENABLE ROW LEVEL SECURITY;
            ALTER TABLE {table} FORCE ROW LEVEL SECURITY;
            CREATE POLICY tenant_isolation_{table} ON {table}
                TO {APPLICATION_ROLE}
                USING ({_tenant_expression()})
                WITH CHECK ({_tenant_expression()});
            """
        )

    op.execute(
        f"""
        ALTER TABLE employee_services ENABLE ROW LEVEL SECURITY;
        ALTER TABLE employee_services FORCE ROW LEVEL SECURITY;
        CREATE POLICY tenant_isolation_employee_services ON employee_services
            TO {APPLICATION_ROLE}
            USING (
                EXISTS (
                    SELECT 1 FROM employees
                    WHERE employees.id = employee_services.employee_id
                      AND employees.tenant_id = NULLIF(
                          current_setting('app.tenant_id', true), ''
                      )::uuid
                )
                AND EXISTS (
                    SELECT 1 FROM services
                    WHERE services.id = employee_services.service_id
                      AND services.tenant_id = NULLIF(
                          current_setting('app.tenant_id', true), ''
                      )::uuid
                )
            )
            WITH CHECK (
                EXISTS (
                    SELECT 1 FROM employees
                    WHERE employees.id = employee_services.employee_id
                      AND employees.tenant_id = NULLIF(
                          current_setting('app.tenant_id', true), ''
                      )::uuid
                )
                AND EXISTS (
                    SELECT 1 FROM services
                    WHERE services.id = employee_services.service_id
                      AND services.tenant_id = NULLIF(
                          current_setting('app.tenant_id', true), ''
                      )::uuid
                )
            );

        ALTER TABLE appointment_services ENABLE ROW LEVEL SECURITY;
        ALTER TABLE appointment_services FORCE ROW LEVEL SECURITY;
        CREATE POLICY tenant_isolation_appointment_services ON appointment_services
            TO {APPLICATION_ROLE}
            USING (
                EXISTS (
                    SELECT 1 FROM appointments
                    WHERE appointments.id = appointment_services.appointment_id
                      AND appointments.tenant_id = NULLIF(
                          current_setting('app.tenant_id', true), ''
                      )::uuid
                )
            )
            WITH CHECK (
                EXISTS (
                    SELECT 1 FROM appointments
                    WHERE appointments.id = appointment_services.appointment_id
                      AND appointments.tenant_id = NULLIF(
                          current_setting('app.tenant_id', true), ''
                      )::uuid
                )
                AND EXISTS (
                    SELECT 1 FROM services
                    WHERE services.id = appointment_services.service_id
                      AND services.tenant_id = NULLIF(
                          current_setting('app.tenant_id', true), ''
                      )::uuid
                )
            );
        """
    )


def downgrade() -> None:
    for table in ("appointment_services", "employee_services"):
        op.execute(
            f"""
            DROP POLICY IF EXISTS tenant_isolation_{table} ON {table};
            ALTER TABLE {table} NO FORCE ROW LEVEL SECURITY;
            ALTER TABLE {table} DISABLE ROW LEVEL SECURITY;
            """
        )

    for table in reversed(DIRECT_TENANT_TABLES):
        op.execute(
            f"""
            DROP POLICY IF EXISTS tenant_isolation_{table} ON {table};
            ALTER TABLE {table} NO FORCE ROW LEVEL SECURITY;
            ALTER TABLE {table} DISABLE ROW LEVEL SECURITY;
            """
        )

    op.execute(
        """
        DROP POLICY IF EXISTS tenant_isolation_tenants ON tenants;
        ALTER TABLE tenants NO FORCE ROW LEVEL SECURITY;
        ALTER TABLE tenants DISABLE ROW LEVEL SECURITY;

        DROP FUNCTION IF EXISTS public.app_create_tenant_with_owner(
            uuid, text, text, uuid, uuid
        );
        DROP FUNCTION IF EXISTS public.app_list_active_tenants(uuid);
        DROP FUNCTION IF EXISTS public.app_list_active_memberships(uuid);
        DROP FUNCTION IF EXISTS public.app_get_active_membership(uuid, uuid);

        REVOKE SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public
            FROM bsrm_booking_app;
        REVOKE USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public FROM bsrm_booking_app;
        REVOKE USAGE ON SCHEMA public FROM bsrm_booking_app;
        ALTER DEFAULT PRIVILEGES IN SCHEMA public
            REVOKE SELECT, INSERT, UPDATE, DELETE ON TABLES FROM bsrm_booking_app;
        ALTER DEFAULT PRIVILEGES IN SCHEMA public
            REVOKE USAGE, SELECT ON SEQUENCES FROM bsrm_booking_app;
        """
    )
