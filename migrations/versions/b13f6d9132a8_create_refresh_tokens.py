"""create refresh tokens

Revision ID: b13f6d9132a8
Revises: 7a8120a27240
Create Date: 2026-08-10

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "b13f6d9132a8"
down_revision: Union[str, Sequence[str], None] = "7a8120a27240"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "refresh_tokens",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("replaced_by_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["replaced_by_id"],
            ["refresh_tokens.id"],
            name=op.f("fk_refresh_tokens_replaced_by_id_refresh_tokens"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_refresh_tokens_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_refresh_tokens")),
        sa.UniqueConstraint(
            "token_hash", name=op.f("uq_refresh_tokens_token_hash")
        ),
    )
    op.create_index(
        op.f("ix_refresh_tokens_expires_at"),
        "refresh_tokens",
        ["expires_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_refresh_tokens_replaced_by_id"),
        "refresh_tokens",
        ["replaced_by_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_refresh_tokens_user_id"),
        "refresh_tokens",
        ["user_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_refresh_tokens_user_id"), table_name="refresh_tokens"
    )
    op.drop_index(
        op.f("ix_refresh_tokens_replaced_by_id"),
        table_name="refresh_tokens",
    )
    op.drop_index(
        op.f("ix_refresh_tokens_expires_at"), table_name="refresh_tokens"
    )
    op.drop_table("refresh_tokens")
