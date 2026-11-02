"""create services and employee services

Revision ID: e681681b7ba7
Revises: 1b9a62cbd6c2
Create Date: 2026-08-03 20:17:17.687084

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e681681b7ba7'
down_revision: Union[str, Sequence[str], None] = '1b9a62cbd6c2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "services",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("location_id", sa.UUID(), nullable=True),
        sa.Column("name", sa.String(length=150), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("duration_minutes", sa.Integer(), nullable=False),
        sa.Column("buffer_before_minutes", sa.Integer(), server_default="0", nullable=False),
        sa.Column("buffer_after_minutes", sa.Integer(), server_default="0", nullable=False),
        sa.Column("price_cents", sa.Integer(), nullable=True),
        sa.Column("currency", sa.String(length=3), server_default="EUR", nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("buffer_after_minutes >= 0", name=op.f("ck_services_buffer_after_minutes_nonnegative")),
        sa.CheckConstraint("buffer_before_minutes >= 0", name=op.f("ck_services_buffer_before_minutes_nonnegative")),
        sa.CheckConstraint("length(currency) = 3", name=op.f("ck_services_currency_length")),
        sa.CheckConstraint("duration_minutes > 0", name=op.f("ck_services_duration_minutes_positive")),
        sa.CheckConstraint("price_cents IS NULL OR price_cents >= 0", name=op.f("ck_services_price_cents_nonnegative")),
        sa.ForeignKeyConstraint(
            ["location_id"], ["locations.id"], name=op.f("fk_services_location_id_locations"), ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"], ["tenants.id"], name=op.f("fk_services_tenant_id_tenants"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_services")),
    )
    op.create_index(op.f("ix_services_location_id"), "services", ["location_id"])
    op.create_index(op.f("ix_services_tenant_id"), "services", ["tenant_id"])
    op.create_table(
        "employee_services",
        sa.Column("employee_id", sa.UUID(), nullable=False),
        sa.Column("service_id", sa.UUID(), nullable=False),
        sa.Column("custom_duration_minutes", sa.Integer(), nullable=True),
        sa.Column("custom_price_cents", sa.Integer(), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint(
            "custom_duration_minutes IS NULL OR custom_duration_minutes > 0",
            name=op.f("ck_employee_services_custom_duration_minutes_positive"),
        ),
        sa.CheckConstraint(
            "custom_price_cents IS NULL OR custom_price_cents >= 0",
            name=op.f("ck_employee_services_custom_price_cents_nonnegative"),
        ),
        sa.ForeignKeyConstraint(
            ["employee_id"], ["employees.id"], name=op.f("fk_employee_services_employee_id_employees"), ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["service_id"], ["services.id"], name=op.f("fk_employee_services_service_id_services"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("employee_id", "service_id", name=op.f("pk_employee_services")),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table("employee_services")
    op.drop_index(op.f("ix_services_tenant_id"), table_name="services")
    op.drop_index(op.f("ix_services_location_id"), table_name="services")
    op.drop_table("services")
