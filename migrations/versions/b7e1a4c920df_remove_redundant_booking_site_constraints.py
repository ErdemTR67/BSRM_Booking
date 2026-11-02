"""remove redundant booking site unique constraints

Revision ID: b7e1a4c920df
Revises: 9d2f6c7a81b4
Create Date: 2026-08-17

"""
from typing import Sequence, Union

from alembic import op


revision: str = "b7e1a4c920df"
down_revision: Union[str, Sequence[str], None] = "9d2f6c7a81b4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_constraint(
        op.f("uq_booking_sites_publishable_key_hash"),
        "booking_sites",
        type_="unique",
    )
    op.drop_constraint(
        op.f("uq_booking_sites_tenant_id"),
        "booking_sites",
        type_="unique",
    )


def downgrade() -> None:
    op.create_unique_constraint(
        op.f("uq_booking_sites_tenant_id"),
        "booking_sites",
        ["tenant_id"],
    )
    op.create_unique_constraint(
        op.f("uq_booking_sites_publishable_key_hash"),
        "booking_sites",
        ["publishable_key_hash"],
    )
