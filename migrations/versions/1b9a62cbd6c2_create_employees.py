"""create employees

Revision ID: 1b9a62cbd6c2
Revises: 1525ee512474
Create Date: 2026-08-03 20:17:16.754701

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '1b9a62cbd6c2'
down_revision: Union[str, Sequence[str], None] = '1525ee512474'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "employees",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("location_id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=True),
        sa.Column("first_name", sa.String(length=100), nullable=False),
        sa.Column("last_name", sa.String(length=100), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=True),
        sa.Column("phone", sa.String(length=50), nullable=True),
        sa.Column("display_color", sa.String(length=20), nullable=True),
        sa.Column("is_bookable", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(
            ["location_id"], ["locations.id"], name=op.f("fk_employees_location_id_locations"), ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"], ["tenants.id"], name=op.f("fk_employees_tenant_id_tenants"), ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name=op.f("fk_employees_user_id_users"), ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_employees")),
    )
    op.create_index(op.f("ix_employees_location_id"), "employees", ["location_id"])
    op.create_index(op.f("ix_employees_tenant_id"), "employees", ["tenant_id"])
    op.create_index(op.f("ix_employees_user_id"), "employees", ["user_id"])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f("ix_employees_user_id"), table_name="employees")
    op.drop_index(op.f("ix_employees_tenant_id"), table_name="employees")
    op.drop_index(op.f("ix_employees_location_id"), table_name="employees")
    op.drop_table("employees")
