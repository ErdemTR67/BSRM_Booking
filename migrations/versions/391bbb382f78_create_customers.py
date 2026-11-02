"""create customers

Revision ID: 391bbb382f78
Revises: 7f499173dc73
Create Date: 2026-08-03 20:17:21.367067

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '391bbb382f78'
down_revision: Union[str, Sequence[str], None] = '7f499173dc73'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "customers",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("first_name", sa.String(length=100), nullable=False),
        sa.Column("last_name", sa.String(length=100), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=True),
        sa.Column("phone", sa.String(length=50), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("marketing_consent", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(
            ["tenant_id"], ["tenants.id"], name=op.f("fk_customers_tenant_id_tenants"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_customers")),
    )
    op.create_index(op.f("ix_customers_tenant_id"), "customers", ["tenant_id"])
    op.create_index("ix_customers_tenant_id_email", "customers", ["tenant_id", "email"])
    op.create_index("ix_customers_tenant_id_phone", "customers", ["tenant_id", "phone"])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ix_customers_tenant_id_phone", table_name="customers")
    op.drop_index("ix_customers_tenant_id_email", table_name="customers")
    op.drop_index(op.f("ix_customers_tenant_id"), table_name="customers")
    op.drop_table("customers")
