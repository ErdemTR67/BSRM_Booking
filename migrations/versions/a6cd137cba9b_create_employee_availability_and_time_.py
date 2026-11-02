"""create employee availability and time off

Revision ID: a6cd137cba9b
Revises: 95ad1fad5544
Create Date: 2026-08-03 20:17:19.643530

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a6cd137cba9b'
down_revision: Union[str, Sequence[str], None] = '95ad1fad5544'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "employee_availabilities",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("employee_id", sa.UUID(), nullable=False),
        sa.Column("weekday", sa.SmallInteger(), nullable=False),
        sa.Column("starts_at", sa.Time(), nullable=False),
        sa.Column("ends_at", sa.Time(), nullable=False),
        sa.Column("valid_from", sa.Date(), nullable=True),
        sa.Column("valid_until", sa.Date(), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint(
            "valid_until IS NULL OR valid_from IS NULL OR valid_until >= valid_from",
            name=op.f("ck_employee_availabilities_date_range_valid"),
        ),
        sa.CheckConstraint("starts_at < ends_at", name=op.f("ck_employee_availabilities_time_range_valid")),
        sa.CheckConstraint("weekday BETWEEN 0 AND 6", name=op.f("ck_employee_availabilities_weekday_range")),
        sa.ForeignKeyConstraint(
            ["employee_id"], ["employees.id"], name=op.f("fk_employee_availabilities_employee_id_employees"), ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"], ["tenants.id"], name=op.f("fk_employee_availabilities_tenant_id_tenants"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_employee_availabilities")),
    )
    op.create_index(
        "ix_employee_availabilities_employee_id_weekday",
        "employee_availabilities",
        ["employee_id", "weekday"],
    )
    op.create_index(op.f("ix_employee_availabilities_tenant_id"), "employee_availabilities", ["tenant_id"])
    op.create_table(
        "time_off",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("employee_id", sa.UUID(), nullable=False),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ends_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("reason", sa.String(length=255), nullable=True),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint(
            "status IN ('pending', 'approved', 'rejected', 'cancelled')",
            name=op.f("ck_time_off_status_allowed"),
        ),
        sa.CheckConstraint("starts_at < ends_at", name=op.f("ck_time_off_time_range_valid")),
        sa.ForeignKeyConstraint(
            ["employee_id"], ["employees.id"], name=op.f("fk_time_off_employee_id_employees"), ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"], ["tenants.id"], name=op.f("fk_time_off_tenant_id_tenants"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_time_off")),
    )
    op.create_index(
        "ix_time_off_employee_id_starts_at_ends_at", "time_off", ["employee_id", "starts_at", "ends_at"]
    )
    op.create_index(op.f("ix_time_off_tenant_id"), "time_off", ["tenant_id"])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f("ix_time_off_tenant_id"), table_name="time_off")
    op.drop_index("ix_time_off_employee_id_starts_at_ends_at", table_name="time_off")
    op.drop_table("time_off")
    op.drop_index(op.f("ix_employee_availabilities_tenant_id"), table_name="employee_availabilities")
    op.drop_index("ix_employee_availabilities_employee_id_weekday", table_name="employee_availabilities")
    op.drop_table("employee_availabilities")
