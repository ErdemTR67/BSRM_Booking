"""create opening hours

Revision ID: 95ad1fad5544
Revises: e681681b7ba7
Create Date: 2026-08-03 20:17:18.658922

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '95ad1fad5544'
down_revision: Union[str, Sequence[str], None] = 'e681681b7ba7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "opening_hours",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("location_id", sa.UUID(), nullable=False),
        sa.Column("weekday", sa.SmallInteger(), nullable=False),
        sa.Column("starts_at", sa.Time(), nullable=False),
        sa.Column("ends_at", sa.Time(), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("starts_at < ends_at", name=op.f("ck_opening_hours_time_range_valid")),
        sa.CheckConstraint("weekday BETWEEN 0 AND 6", name=op.f("ck_opening_hours_weekday_range")),
        sa.ForeignKeyConstraint(
            ["location_id"], ["locations.id"], name=op.f("fk_opening_hours_location_id_locations"), ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"], ["tenants.id"], name=op.f("fk_opening_hours_tenant_id_tenants"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_opening_hours")),
    )
    op.create_index("ix_opening_hours_location_id_weekday", "opening_hours", ["location_id", "weekday"])
    op.create_index(op.f("ix_opening_hours_tenant_id"), "opening_hours", ["tenant_id"])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f("ix_opening_hours_tenant_id"), table_name="opening_hours")
    op.drop_index("ix_opening_hours_location_id_weekday", table_name="opening_hours")
    op.drop_table("opening_hours")
