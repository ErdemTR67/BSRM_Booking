"""create location closures

Revision ID: 7f499173dc73
Revises: a6cd137cba9b
Create Date: 2026-08-03 20:17:20.434421

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '7f499173dc73'
down_revision: Union[str, Sequence[str], None] = 'a6cd137cba9b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "location_closures",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("location_id", sa.UUID(), nullable=False),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ends_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("reason", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("starts_at < ends_at", name=op.f("ck_location_closures_time_range_valid")),
        sa.ForeignKeyConstraint(
            ["location_id"], ["locations.id"], name=op.f("fk_location_closures_location_id_locations"), ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"], ["tenants.id"], name=op.f("fk_location_closures_tenant_id_tenants"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_location_closures")),
    )
    op.create_index(
        "ix_location_closures_location_id_starts_at_ends_at",
        "location_closures",
        ["location_id", "starts_at", "ends_at"],
    )
    op.create_index(op.f("ix_location_closures_tenant_id"), "location_closures", ["tenant_id"])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f("ix_location_closures_tenant_id"), table_name="location_closures")
    op.drop_index("ix_location_closures_location_id_starts_at_ends_at", table_name="location_closures")
    op.drop_table("location_closures")
