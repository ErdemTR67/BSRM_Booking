"""prevent overlapping appointments

Revision ID: 7a8120a27240
Revises: 207dcf6f521e
Create Date: 2026-08-03 20:17:23.136886

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '7a8120a27240'
down_revision: Union[str, Sequence[str], None] = '207dcf6f521e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.execute("CREATE EXTENSION IF NOT EXISTS btree_gist")
    op.execute(
        """
        ALTER TABLE appointments
        ADD CONSTRAINT excl_appointments_employee_time_overlap
        EXCLUDE USING gist (
            employee_id WITH =,
            tstzrange(starts_at, ends_at, '[)') WITH &&
        )
        WHERE (status IN ('pending', 'confirmed'))
        """
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.execute(
        "ALTER TABLE appointments "
        "DROP CONSTRAINT IF EXISTS excl_appointments_employee_time_overlap"
    )
    # btree_gist is intentionally retained because other database objects may use it.
