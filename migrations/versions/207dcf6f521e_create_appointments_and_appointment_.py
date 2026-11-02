"""create appointments and appointment services

Revision ID: 207dcf6f521e
Revises: 391bbb382f78
Create Date: 2026-08-03 20:17:22.232493

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '207dcf6f521e'
down_revision: Union[str, Sequence[str], None] = '391bbb382f78'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "appointments",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("location_id", sa.UUID(), nullable=False),
        sa.Column("employee_id", sa.UUID(), nullable=False),
        sa.Column("customer_id", sa.UUID(), nullable=True),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ends_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("customer_name", sa.String(length=201), nullable=False),
        sa.Column("customer_email", sa.String(length=255), nullable=True),
        sa.Column("customer_phone", sa.String(length=50), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("cancellation_reason", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint(
            "status IN ('pending', 'confirmed', 'completed', 'cancelled', 'no_show')",
            name=op.f("ck_appointments_status_allowed"),
        ),
        sa.CheckConstraint("starts_at < ends_at", name=op.f("ck_appointments_time_range_valid")),
        sa.ForeignKeyConstraint(
            ["customer_id"], ["customers.id"], name=op.f("fk_appointments_customer_id_customers"), ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["employee_id"], ["employees.id"], name=op.f("fk_appointments_employee_id_employees"), ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["location_id"], ["locations.id"], name=op.f("fk_appointments_location_id_locations"), ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"], ["tenants.id"], name=op.f("fk_appointments_tenant_id_tenants"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_appointments")),
    )
    op.create_index(op.f("ix_appointments_customer_id"), "appointments", ["customer_id"])
    op.create_index(op.f("ix_appointments_employee_id"), "appointments", ["employee_id"])
    op.create_index("ix_appointments_employee_id_starts_at", "appointments", ["employee_id", "starts_at"])
    op.create_index(op.f("ix_appointments_location_id"), "appointments", ["location_id"])
    op.create_index("ix_appointments_location_id_starts_at", "appointments", ["location_id", "starts_at"])
    op.create_index(op.f("ix_appointments_status"), "appointments", ["status"])
    op.create_index(op.f("ix_appointments_tenant_id"), "appointments", ["tenant_id"])
    op.create_table(
        "appointment_services",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("appointment_id", sa.UUID(), nullable=False),
        sa.Column("service_id", sa.UUID(), nullable=False),
        sa.Column("service_name", sa.String(length=150), nullable=False),
        sa.Column("duration_minutes", sa.Integer(), nullable=False),
        sa.Column("price_cents", sa.Integer(), nullable=True),
        sa.Column("position", sa.Integer(), server_default="0", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("duration_minutes > 0", name=op.f("ck_appointment_services_duration_minutes_positive")),
        sa.CheckConstraint(
            "price_cents IS NULL OR price_cents >= 0",
            name=op.f("ck_appointment_services_price_cents_nonnegative"),
        ),
        sa.CheckConstraint("position >= 0", name=op.f("ck_appointment_services_position_nonnegative")),
        sa.ForeignKeyConstraint(
            ["appointment_id"], ["appointments.id"], name=op.f("fk_appointment_services_appointment_id_appointments"), ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["service_id"], ["services.id"], name=op.f("fk_appointment_services_service_id_services"), ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_appointment_services")),
        sa.UniqueConstraint(
            "appointment_id", "position", name="uq_appointment_services_appointment_id_position"
        ),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table("appointment_services")
    op.drop_index(op.f("ix_appointments_tenant_id"), table_name="appointments")
    op.drop_index(op.f("ix_appointments_status"), table_name="appointments")
    op.drop_index("ix_appointments_location_id_starts_at", table_name="appointments")
    op.drop_index(op.f("ix_appointments_location_id"), table_name="appointments")
    op.drop_index("ix_appointments_employee_id_starts_at", table_name="appointments")
    op.drop_index(op.f("ix_appointments_employee_id"), table_name="appointments")
    op.drop_index(op.f("ix_appointments_customer_id"), table_name="appointments")
    op.drop_table("appointments")
