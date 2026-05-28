"""add effect and photo_filter columns to event

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-05-28 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

revision = 'b2c3d4e5f6a7'
down_revision = 'a1b2c3d4e5f6'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('event', schema=None) as batch_op:
        batch_op.add_column(sa.Column('effect', sa.String(40), nullable=True, server_default='none'))
        batch_op.add_column(sa.Column('photo_filter', sa.String(40), nullable=True, server_default='none'))


def downgrade():
    with op.batch_alter_table('event', schema=None) as batch_op:
        batch_op.drop_column('photo_filter')
        batch_op.drop_column('effect')
