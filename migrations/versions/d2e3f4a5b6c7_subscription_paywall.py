"""add subscription fields, payment table, event.is_live

Revision ID: d2e3f4a5b6c7
Revises: c1d2e3f4a5b6
Create Date: 2026-05-29 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

revision = 'd2e3f4a5b6c7'
down_revision = 'c1d2e3f4a5b6'
branch_labels = None
depends_on = None


def upgrade():
    # User — subscription fields
    with op.batch_alter_table('user', schema=None) as batch_op:
        batch_op.add_column(sa.Column('sub_status',   sa.String(20),  nullable=True, server_default='free'))
        batch_op.add_column(sa.Column('sub_pf_token', sa.String(200), nullable=True, server_default=''))
        batch_op.add_column(sa.Column('sub_expires',  sa.DateTime(),  nullable=True))

    # Event — is_live; default 1 (true) so ALL existing events stay accessible
    with op.batch_alter_table('event', schema=None) as batch_op:
        batch_op.add_column(sa.Column('is_live', sa.Boolean(), nullable=False, server_default='1'))

    # Payment table
    op.create_table(
        'payment',
        sa.Column('id',            sa.Integer(),      nullable=False, primary_key=True),
        sa.Column('user_id',       sa.Integer(),      nullable=False),
        sa.Column('pf_payment_id', sa.String(100),    nullable=True, server_default=''),
        sa.Column('pf_sub_token',  sa.String(200),    nullable=True, server_default=''),
        sa.Column('amount',        sa.Numeric(10, 2), nullable=True, server_default='0'),
        sa.Column('status',        sa.String(20),     nullable=True, server_default='pending'),
        sa.Column('created_at',    sa.DateTime(),     nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['user.id'], ondelete='CASCADE'),
    )


def downgrade():
    op.drop_table('payment')
    with op.batch_alter_table('event', schema=None) as batch_op:
        batch_op.drop_column('is_live')
    with op.batch_alter_table('user', schema=None) as batch_op:
        batch_op.drop_column('sub_expires')
        batch_op.drop_column('sub_pf_token')
        batch_op.drop_column('sub_status')
