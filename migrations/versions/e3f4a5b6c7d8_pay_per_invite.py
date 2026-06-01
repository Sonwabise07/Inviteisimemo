"""pay-per-invite: event.single_paid, payment.kind, payment.event_id

Revision ID: e3f4a5b6c7d8
Revises: d2e3f4a5b6c7
Create Date: 2026-06-01 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

revision = 'e3f4a5b6c7d8'
down_revision = 'd2e3f4a5b6c7'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('event', schema=None) as batch_op:
        batch_op.add_column(sa.Column('single_paid', sa.Boolean(),
                                      nullable=False, server_default='0'))

    with op.batch_alter_table('payment', schema=None) as batch_op:
        batch_op.add_column(sa.Column('kind', sa.String(20),
                                      nullable=True, server_default='subscription'))
        batch_op.add_column(sa.Column('event_id', sa.Integer(), nullable=True))


def downgrade():
    with op.batch_alter_table('payment', schema=None) as batch_op:
        batch_op.drop_column('event_id')
        batch_op.drop_column('kind')
    with op.batch_alter_table('event', schema=None) as batch_op:
        batch_op.drop_column('single_paid')
