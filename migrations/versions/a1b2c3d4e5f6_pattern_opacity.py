"""add pattern_opacity column to event

Revision ID: a1b2c3d4e5f6
Revises: f3a9c1b72e88
Create Date: 2026-05-28 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

revision = 'a1b2c3d4e5f6'
down_revision = 'f3a9c1b72e88'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('event', schema=None) as batch_op:
        batch_op.add_column(sa.Column('pattern_opacity', sa.Integer(), nullable=True, server_default='40'))


def downgrade():
    with op.batch_alter_table('event', schema=None) as batch_op:
        batch_op.drop_column('pattern_opacity')
