"""add platform admin and tenant invitations

Revision ID: f4c8a1d2e903
Revises: e7b2d40a6c31
Create Date: 2026-08-14

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "f4c8a1d2e903"
down_revision: Union[str, Sequence[str], None] = "e7b2d40a6c31"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


APPLICATION_ROLE = "bsrm_booking_app"


def upgrade() -> None:
    op.create_table(
        "platform_roles",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("role", sa.String(length=30), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "role IN ('platform_admin')",
            name=op.f("ck_platform_roles_role_allowed"),
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_platform_roles_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_platform_roles")),
        sa.UniqueConstraint("user_id", name=op.f("uq_platform_roles_user_id")),
    )
    op.create_index(
        op.f("ix_platform_roles_user_id"),
        "platform_roles",
        ["user_id"],
        unique=True,
    )

    op.create_table(
        "tenant_invitations",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("role", sa.String(length=30), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("accepted_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("invited_by_user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "role IN ('owner', 'admin', 'manager', 'staff')",
            name=op.f("ck_tenant_invitations_role_allowed"),
        ),
        sa.CheckConstraint(
            "accepted_at IS NULL OR revoked_at IS NULL",
            name=op.f("ck_tenant_invitations_not_accepted_and_revoked"),
        ),
        sa.ForeignKeyConstraint(
            ["accepted_user_id"],
            ["users.id"],
            name=op.f("fk_tenant_invitations_accepted_user_id_users"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["invited_by_user_id"],
            ["users.id"],
            name=op.f("fk_tenant_invitations_invited_by_user_id_users"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenants.id"],
            name=op.f("fk_tenant_invitations_tenant_id_tenants"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_tenant_invitations")),
        sa.UniqueConstraint(
            "token_hash", name=op.f("uq_tenant_invitations_token_hash")
        ),
    )
    op.create_index(
        op.f("ix_tenant_invitations_accepted_user_id"),
        "tenant_invitations",
        ["accepted_user_id"],
    )
    op.create_index(
        op.f("ix_tenant_invitations_expires_at"),
        "tenant_invitations",
        ["expires_at"],
    )
    op.create_index(
        op.f("ix_tenant_invitations_invited_by_user_id"),
        "tenant_invitations",
        ["invited_by_user_id"],
    )
    op.create_index(
        op.f("ix_tenant_invitations_tenant_id"),
        "tenant_invitations",
        ["tenant_id"],
    )
    op.create_index(
        "ix_tenant_invitations_tenant_id_email",
        "tenant_invitations",
        ["tenant_id", "email"],
    )
    op.create_index(
        "uq_tenant_invitations_pending_tenant_email",
        "tenant_invitations",
        ["tenant_id", sa.text("lower(email)")],
        unique=True,
        postgresql_where=sa.text("accepted_at IS NULL AND revoked_at IS NULL"),
    )

    op.execute(
        f"""
        GRANT SELECT ON TABLE public.platform_roles TO {APPLICATION_ROLE};
        GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE public.tenant_invitations
            TO {APPLICATION_ROLE};

        REVOKE EXECUTE ON FUNCTION public.app_create_tenant_with_owner(
            uuid, text, text, uuid, uuid
        ) FROM {APPLICATION_ROLE};

        ALTER TABLE public.tenant_invitations ENABLE ROW LEVEL SECURITY;
        ALTER TABLE public.tenant_invitations FORCE ROW LEVEL SECURITY;

        CREATE POLICY platform_admin_tenant_access ON public.tenants
            TO {APPLICATION_ROLE}
            USING (
                EXISTS (
                    SELECT 1
                    FROM public.platform_roles AS platform_role
                    WHERE platform_role.user_id = NULLIF(
                        current_setting('app.user_id', true), ''
                    )::uuid
                      AND platform_role.role = 'platform_admin'
                      AND platform_role.is_active IS TRUE
                )
            )
            WITH CHECK (
                EXISTS (
                    SELECT 1
                    FROM public.platform_roles AS platform_role
                    WHERE platform_role.user_id = NULLIF(
                        current_setting('app.user_id', true), ''
                    )::uuid
                      AND platform_role.role = 'platform_admin'
                      AND platform_role.is_active IS TRUE
                )
            );

        CREATE POLICY platform_admin_invitation_access ON public.tenant_invitations
            TO {APPLICATION_ROLE}
            USING (
                EXISTS (
                    SELECT 1
                    FROM public.platform_roles AS platform_role
                    WHERE platform_role.user_id = NULLIF(
                        current_setting('app.user_id', true), ''
                    )::uuid
                      AND platform_role.role = 'platform_admin'
                      AND platform_role.is_active IS TRUE
                )
            )
            WITH CHECK (
                EXISTS (
                    SELECT 1
                    FROM public.platform_roles AS platform_role
                    WHERE platform_role.user_id = NULLIF(
                        current_setting('app.user_id', true), ''
                    )::uuid
                      AND platform_role.role = 'platform_admin'
                      AND platform_role.is_active IS TRUE
                )
            );
        """
    )

    op.execute(
        """
        CREATE FUNCTION public.app_get_invitation_for_acceptance(
            p_token_hash text
        ) RETURNS SETOF public.tenant_invitations
        LANGUAGE plpgsql
        VOLATILE
        SECURITY DEFINER
        SET search_path = pg_catalog, public
        AS $function$
        BEGIN
            RETURN QUERY
            SELECT invitation.*
            FROM public.tenant_invitations AS invitation
            JOIN public.tenants AS tenant ON tenant.id = invitation.tenant_id
            WHERE invitation.token_hash = p_token_hash
              AND invitation.accepted_at IS NULL
              AND invitation.revoked_at IS NULL
              AND invitation.expires_at > CURRENT_TIMESTAMP
              AND tenant.is_active IS TRUE
            FOR UPDATE OF invitation;
        END
        $function$;

        CREATE FUNCTION public.app_accept_tenant_invitation(
            p_token_hash text,
            p_user_id uuid,
            p_membership_id uuid
        ) RETURNS public.memberships
        LANGUAGE plpgsql
        VOLATILE
        SECURITY DEFINER
        SET search_path = pg_catalog, public
        AS $function$
        DECLARE
            selected_invitation public.tenant_invitations;
            accepted_membership public.memberships;
        BEGIN
            SELECT invitation.*
            INTO selected_invitation
            FROM public.tenant_invitations AS invitation
            JOIN public.tenants AS tenant ON tenant.id = invitation.tenant_id
            WHERE invitation.token_hash = p_token_hash
              AND invitation.accepted_at IS NULL
              AND invitation.revoked_at IS NULL
              AND invitation.expires_at > CURRENT_TIMESTAMP
              AND tenant.is_active IS TRUE
            FOR UPDATE OF invitation;

            IF NOT FOUND THEN
                RAISE EXCEPTION 'Invitation is invalid or expired'
                    USING ERRCODE = '28000';
            END IF;

            IF NOT EXISTS (
                SELECT 1
                FROM public.users AS app_user
                WHERE app_user.id = p_user_id
                  AND app_user.is_active IS TRUE
                  AND lower(app_user.email) = lower(selected_invitation.email)
            ) THEN
                RAISE EXCEPTION 'Invitation does not match the user'
                    USING ERRCODE = '28000';
            END IF;

            INSERT INTO public.memberships (
                id, tenant_id, user_id, role, is_active
            ) VALUES (
                p_membership_id,
                selected_invitation.tenant_id,
                p_user_id,
                selected_invitation.role,
                TRUE
            )
            ON CONFLICT (tenant_id, user_id)
            DO UPDATE SET
                role = EXCLUDED.role,
                is_active = TRUE,
                updated_at = CURRENT_TIMESTAMP
            RETURNING * INTO accepted_membership;

            UPDATE public.tenant_invitations
            SET accepted_at = CURRENT_TIMESTAMP,
                accepted_user_id = p_user_id
            WHERE id = selected_invitation.id;

            RETURN accepted_membership;
        END
        $function$;

        REVOKE ALL ON FUNCTION public.app_get_invitation_for_acceptance(text)
            FROM PUBLIC;
        REVOKE ALL ON FUNCTION public.app_accept_tenant_invitation(text, uuid, uuid)
            FROM PUBLIC;
        GRANT EXECUTE ON FUNCTION public.app_get_invitation_for_acceptance(text)
            TO bsrm_booking_app;
        GRANT EXECUTE ON FUNCTION public.app_accept_tenant_invitation(text, uuid, uuid)
            TO bsrm_booking_app;
        """
    )


def downgrade() -> None:
    op.execute(
        f"""
        DROP FUNCTION IF EXISTS public.app_accept_tenant_invitation(text, uuid, uuid);
        DROP FUNCTION IF EXISTS public.app_get_invitation_for_acceptance(text);

        DROP POLICY IF EXISTS platform_admin_invitation_access
            ON public.tenant_invitations;
        ALTER TABLE public.tenant_invitations NO FORCE ROW LEVEL SECURITY;
        ALTER TABLE public.tenant_invitations DISABLE ROW LEVEL SECURITY;

        DROP POLICY IF EXISTS platform_admin_tenant_access ON public.tenants;

        GRANT EXECUTE ON FUNCTION public.app_create_tenant_with_owner(
            uuid, text, text, uuid, uuid
        ) TO {APPLICATION_ROLE};

        REVOKE SELECT, INSERT, UPDATE, DELETE
            ON TABLE public.tenant_invitations FROM {APPLICATION_ROLE};
        REVOKE SELECT ON TABLE public.platform_roles FROM {APPLICATION_ROLE};
        """
    )

    op.drop_index(
        "uq_tenant_invitations_pending_tenant_email",
        table_name="tenant_invitations",
    )
    op.drop_index(
        "ix_tenant_invitations_tenant_id_email",
        table_name="tenant_invitations",
    )
    op.drop_index(
        op.f("ix_tenant_invitations_tenant_id"),
        table_name="tenant_invitations",
    )
    op.drop_index(
        op.f("ix_tenant_invitations_invited_by_user_id"),
        table_name="tenant_invitations",
    )
    op.drop_index(
        op.f("ix_tenant_invitations_expires_at"),
        table_name="tenant_invitations",
    )
    op.drop_index(
        op.f("ix_tenant_invitations_accepted_user_id"),
        table_name="tenant_invitations",
    )
    op.drop_table("tenant_invitations")
    op.drop_index(op.f("ix_platform_roles_user_id"), table_name="platform_roles")
    op.drop_table("platform_roles")
