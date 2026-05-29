"""add reaction table and rsvp.plus_ones column

Revision ID: c1d2e3f4a5b6
Revises: b2c3d4e5f6a7
Create Date: 2026-05-29 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

revision = 'c1d2e3f4a5b6'
down_revision = 'b2c3d4e5f6a7'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'reaction',
        sa.Column('id',         sa.Integer(),     nullable=False, primary_key=True),
        sa.Column('event_id',   sa.Integer(),     nullable=False),
        sa.Column('emoji',      sa.String(10),    nullable=False),
        sa.Column('ip_hash',    sa.String(64),    nullable=True, server_default=''),
        sa.Column('created_at', sa.DateTime(),    nullable=True),
        sa.ForeignKeyConstraint(['event_id'], ['event.id'], ondelete='CASCADE'),
    )
    with op.batch_alter_table('rsvp', schema=None) as batch_op:
        batch_op.add_column(sa.Column('plus_ones', sa.Integer(), nullable=True, server_default='0'))


def downgrade():
    with op.batch_alter_table('rsvp', schema=None) as batch_op:
        batch_op.drop_column('plus_ones')
    op.drop_table('reaction')
