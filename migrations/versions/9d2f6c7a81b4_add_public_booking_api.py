"""add public booking API

Revision ID: 9d2f6c7a81b4
Revises: f4c8a1d2e903
Create Date: 2026-08-17

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "9d2f6c7a81b4"
down_revision: Union[str, Sequence[str], None] = "f4c8a1d2e903"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

APPLICATION_ROLE = "bsrm_booking_app"


def upgrade() -> None:
    op.add_column(
        "appointments",
        sa.Column("public_reference", sa.String(length=24), nullable=True),
    )
    op.create_unique_constraint(
        op.f("uq_appointments_public_reference"),
        "appointments",
        ["public_reference"],
    )

    op.create_table(
        "booking_sites",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=150), nullable=False),
        sa.Column("publishable_key_hash", sa.String(length=64), nullable=False),
        sa.Column("key_prefix", sa.String(length=24), nullable=False),
        sa.Column(
            "allowed_origins",
            postgresql.ARRAY(sa.String(length=255)),
            server_default="{}",
            nullable=False,
        ),
        sa.Column("default_location_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("slot_interval_minutes", sa.Integer(), server_default="15", nullable=False),
        sa.Column("minimum_notice_minutes", sa.Integer(), server_default="60", nullable=False),
        sa.Column("maximum_advance_days", sa.Integer(), server_default="90", nullable=False),
        sa.Column("require_phone", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("booking_enabled", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint(
            "maximum_advance_days BETWEEN 1 AND 365",
            name=op.f("ck_booking_sites_maximum_advance_range"),
        ),
        sa.CheckConstraint(
            "minimum_notice_minutes >= 0",
            name=op.f("ck_booking_sites_minimum_notice_nonnegative"),
        ),
        sa.CheckConstraint(
            "slot_interval_minutes BETWEEN 5 AND 120",
            name=op.f("ck_booking_sites_slot_interval_range"),
        ),
        sa.ForeignKeyConstraint(
            ["default_location_id"], ["locations.id"],
            name=op.f("fk_booking_sites_default_location_id_locations"), ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"], ["tenants.id"],
            name=op.f("fk_booking_sites_tenant_id_tenants"), ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_booking_sites")),
        sa.UniqueConstraint("publishable_key_hash", name=op.f("uq_booking_sites_publishable_key_hash")),
        sa.UniqueConstraint("tenant_id", name=op.f("uq_booking_sites_tenant_id")),
    )
    op.create_index(op.f("ix_booking_sites_publishable_key_hash"), "booking_sites", ["publishable_key_hash"], unique=True)
    op.create_index(op.f("ix_booking_sites_tenant_id"), "booking_sites", ["tenant_id"], unique=True)

    op.create_table(
        "public_booking_idempotency",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("booking_site_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("idempotency_key", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("request_hash", sa.String(length=64), nullable=False),
        sa.Column("appointment_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(
            ["appointment_id"], ["appointments.id"],
            name=op.f("fk_public_booking_idempotency_appointment_id_appointments"), ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["booking_site_id"], ["booking_sites.id"],
            name=op.f("fk_public_booking_idempotency_booking_site_id_booking_sites"), ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"], ["tenants.id"],
            name=op.f("fk_public_booking_idempotency_tenant_id_tenants"), ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_public_booking_idempotency")),
        sa.UniqueConstraint(
            "booking_site_id", "idempotency_key",
            name="uq_public_booking_idempotency_site_key",
        ),
    )
    op.create_index(op.f("ix_public_booking_idempotency_booking_site_id"), "public_booking_idempotency", ["booking_site_id"])
    op.create_index(op.f("ix_public_booking_idempotency_tenant_id"), "public_booking_idempotency", ["tenant_id"])

    op.create_table(
        "public_booking_rate_limits",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("booking_site_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("client_hash", sa.String(length=64), nullable=False),
        sa.Column("action", sa.String(length=30), nullable=False),
        sa.Column("window_started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("request_count", sa.Integer(), server_default="1", nullable=False),
        sa.ForeignKeyConstraint(
            ["booking_site_id"], ["booking_sites.id"],
            name=op.f("fk_public_booking_rate_limits_booking_site_id_booking_sites"), ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"], ["tenants.id"],
            name=op.f("fk_public_booking_rate_limits_tenant_id_tenants"), ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_public_booking_rate_limits")),
        sa.UniqueConstraint(
            "booking_site_id", "client_hash", "action", "window_started_at",
            name="uq_public_booking_rate_limit_bucket",
        ),
    )
    op.create_index(op.f("ix_public_booking_rate_limits_booking_site_id"), "public_booking_rate_limits", ["booking_site_id"])
    op.create_index(op.f("ix_public_booking_rate_limits_tenant_id"), "public_booking_rate_limits", ["tenant_id"])

    op.execute(
        f"""
        GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE public.booking_sites TO {APPLICATION_ROLE};
        GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE public.public_booking_idempotency TO {APPLICATION_ROLE};
        GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE public.public_booking_rate_limits TO {APPLICATION_ROLE};

        ALTER TABLE public.booking_sites ENABLE ROW LEVEL SECURITY;
        ALTER TABLE public.booking_sites FORCE ROW LEVEL SECURITY;
        ALTER TABLE public.public_booking_idempotency ENABLE ROW LEVEL SECURITY;
        ALTER TABLE public.public_booking_idempotency FORCE ROW LEVEL SECURITY;
        ALTER TABLE public.public_booking_rate_limits ENABLE ROW LEVEL SECURITY;
        ALTER TABLE public.public_booking_rate_limits FORCE ROW LEVEL SECURITY;

        CREATE POLICY tenant_isolation ON public.booking_sites
            TO {APPLICATION_ROLE}
            USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)
            WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);
        CREATE POLICY tenant_isolation ON public.public_booking_idempotency
            TO {APPLICATION_ROLE}
            USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)
            WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);
        CREATE POLICY tenant_isolation ON public.public_booking_rate_limits
            TO {APPLICATION_ROLE}
            USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)
            WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);
        """
    )

    op.execute(
        f"""
        CREATE FUNCTION public.app_resolve_booking_site(p_key_hash text)
        RETURNS SETOF public.booking_sites
        LANGUAGE sql
        STABLE
        SECURITY DEFINER
        SET search_path = pg_catalog, public
        AS $function$
            SELECT site.*
            FROM public.booking_sites AS site
            JOIN public.tenants AS tenant ON tenant.id = site.tenant_id
            WHERE site.publishable_key_hash = p_key_hash
              AND site.is_active IS TRUE
              AND site.booking_enabled IS TRUE
              AND tenant.is_active IS TRUE
            LIMIT 1
        $function$;

        REVOKE ALL ON FUNCTION public.app_resolve_booking_site(text) FROM PUBLIC;
        GRANT EXECUTE ON FUNCTION public.app_resolve_booking_site(text) TO {APPLICATION_ROLE};
        """
    )


def downgrade() -> None:
    op.execute(
        f"""
        DROP FUNCTION IF EXISTS public.app_resolve_booking_site(text);

        DROP POLICY IF EXISTS tenant_isolation ON public.public_booking_rate_limits;
        DROP POLICY IF EXISTS tenant_isolation ON public.public_booking_idempotency;
        DROP POLICY IF EXISTS tenant_isolation ON public.booking_sites;

        ALTER TABLE public.public_booking_rate_limits NO FORCE ROW LEVEL SECURITY;
        ALTER TABLE public.public_booking_rate_limits DISABLE ROW LEVEL SECURITY;
        ALTER TABLE public.public_booking_idempotency NO FORCE ROW LEVEL SECURITY;
        ALTER TABLE public.public_booking_idempotency DISABLE ROW LEVEL SECURITY;
        ALTER TABLE public.booking_sites NO FORCE ROW LEVEL SECURITY;
        ALTER TABLE public.booking_sites DISABLE ROW LEVEL SECURITY;

        REVOKE SELECT, INSERT, UPDATE, DELETE ON TABLE public.public_booking_rate_limits FROM {APPLICATION_ROLE};
        REVOKE SELECT, INSERT, UPDATE, DELETE ON TABLE public.public_booking_idempotency FROM {APPLICATION_ROLE};
        REVOKE SELECT, INSERT, UPDATE, DELETE ON TABLE public.booking_sites FROM {APPLICATION_ROLE};
        """
    )
    op.drop_index(op.f("ix_public_booking_rate_limits_tenant_id"), table_name="public_booking_rate_limits")
    op.drop_index(op.f("ix_public_booking_rate_limits_booking_site_id"), table_name="public_booking_rate_limits")
    op.drop_table("public_booking_rate_limits")
    op.drop_index(op.f("ix_public_booking_idempotency_tenant_id"), table_name="public_booking_idempotency")
    op.drop_index(op.f("ix_public_booking_idempotency_booking_site_id"), table_name="public_booking_idempotency")
    op.drop_table("public_booking_idempotency")
    op.drop_index(op.f("ix_booking_sites_tenant_id"), table_name="booking_sites")
    op.drop_index(op.f("ix_booking_sites_publishable_key_hash"), table_name="booking_sites")
    op.drop_table("booking_sites")
    op.drop_constraint(op.f("uq_appointments_public_reference"), "appointments", type_="unique")
    op.drop_column("appointments", "public_reference")
