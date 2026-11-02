"""harden application role privileges

Revision ID: e7b2d40a6c31
Revises: c4a91e8d7f20
Create Date: 2026-08-11

"""
from typing import Sequence, Union

from alembic import op


revision: str = "e7b2d40a6c31"
down_revision: Union[str, Sequence[str], None] = "c4a91e8d7f20"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        REVOKE ALL PRIVILEGES ON TABLE alembic_version FROM bsrm_booking_app;
        ALTER DEFAULT PRIVILEGES IN SCHEMA public
            REVOKE SELECT, INSERT, UPDATE, DELETE ON TABLES FROM bsrm_booking_app;
        ALTER DEFAULT PRIVILEGES IN SCHEMA public
            REVOKE USAGE, SELECT ON SEQUENCES FROM bsrm_booking_app;
        """
    )


def downgrade() -> None:
    op.execute(
        """
        GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE alembic_version
            TO bsrm_booking_app;
        ALTER DEFAULT PRIVILEGES IN SCHEMA public
            GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO bsrm_booking_app;
        ALTER DEFAULT PRIVILEGES IN SCHEMA public
            GRANT USAGE, SELECT ON SEQUENCES TO bsrm_booking_app;
        """
    )
