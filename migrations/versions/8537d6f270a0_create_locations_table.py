"""create locations table

Revision ID: 8537d6f270a0
Revises: d7c0c91d421f
Create Date: 2026-08-03 20:07:45.386603

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '8537d6f270a0'
down_revision: Union[str, Sequence[str], None] = 'd7c0c91d421f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('locations',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('tenant_id', sa.UUID(), nullable=False),
    sa.Column('name', sa.String(length=150), nullable=False),
    sa.Column('slug', sa.String(length=100), nullable=False),
    sa.Column('timezone', sa.String(length=50), server_default='Europe/Brussels', nullable=False),
    sa.Column('address_line_1', sa.String(length=255), nullable=True),
    sa.Column('address_line_2', sa.String(length=255), nullable=True),
    sa.Column('postal_code', sa.String(length=20), nullable=True),
    sa.Column('city', sa.String(length=100), nullable=True),
    sa.Column('country_code', sa.String(length=2), server_default='BE', nullable=False),
    sa.Column('is_active', sa.Boolean(), server_default='true', nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], name=op.f('fk_locations_tenant_id_tenants'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_locations')),
    sa.UniqueConstraint('tenant_id', 'slug', name='uq_locations_tenant_id_slug')
    )
    op.create_index(op.f('ix_locations_tenant_id'), 'locations', ['tenant_id'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_locations_tenant_id'), table_name='locations')
    op.drop_table('locations')
