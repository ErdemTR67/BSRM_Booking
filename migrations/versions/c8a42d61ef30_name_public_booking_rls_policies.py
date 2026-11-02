"""name public booking RLS policies

Revision ID: c8a42d61ef30
Revises: b7e1a4c920df
Create Date: 2026-08-17

"""
from typing import Sequence, Union

from alembic import op


revision: str = "c8a42d61ef30"
down_revision: Union[str, Sequence[str], None] = "b7e1a4c920df"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        "ALTER POLICY tenant_isolation ON public.booking_sites "
        "RENAME TO tenant_isolation_booking_sites"
    )
    op.execute(
        "ALTER POLICY tenant_isolation ON public.public_booking_idempotency "
        "RENAME TO tenant_isolation_public_booking_idempotency"
    )
    op.execute(
        "ALTER POLICY tenant_isolation ON public.public_booking_rate_limits "
        "RENAME TO tenant_isolation_public_booking_rate_limits"
    )


def downgrade() -> None:
    op.execute(
        "ALTER POLICY tenant_isolation_public_booking_rate_limits "
        "ON public.public_booking_rate_limits RENAME TO tenant_isolation"
    )
    op.execute(
        "ALTER POLICY tenant_isolation_public_booking_idempotency "
        "ON public.public_booking_idempotency RENAME TO tenant_isolation"
    )
    op.execute(
        "ALTER POLICY tenant_isolation_booking_sites "
        "ON public.booking_sites RENAME TO tenant_isolation"
    )
