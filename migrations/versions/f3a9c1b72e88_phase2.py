"""phase 2 - dual colour, video note, programme, comments, social fields

Revision ID: f3a9c1b72e88
Revises: dada99558376
Create Date: 2026-05-24 20:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

revision = 'f3a9c1b72e88'
down_revision = 'dada99558376'
branch_labels = None
depends_on = None


def upgrade():
    # New columns on event table
    with op.batch_alter_table('event', schema=None) as batch_op:
        batch_op.add_column(sa.Column('accent_colour_2', sa.String(20), nullable=True, server_default=''))
        batch_op.add_column(sa.Column('video_note', sa.String(300), nullable=True, server_default=''))
        batch_op.add_column(sa.Column('programme', sa.Text(), nullable=True, server_default=''))
        batch_op.add_column(sa.Column('whatsapp_group', sa.String(400), nullable=True, server_default=''))
        batch_op.add_column(sa.Column('hashtag', sa.String(80), nullable=True, server_default=''))
        batch_op.add_column(sa.Column('greeting_lang', sa.String(30), nullable=True, server_default='English'))
        batch_op.add_column(sa.Column('spotify_url', sa.String(400), nullable=True, server_default=''))

    # New guest_comment table
    op.create_table(
        'guest_comment',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('event_id', sa.Integer(), sa.ForeignKey('event.id'), nullable=False),
        sa.Column('name', sa.String(120), nullable=False),
        sa.Column('message', sa.Text(), nullable=False),
        sa.Column('approved', sa.Boolean(), default=True, nullable=False, server_default='1'),
        sa.Column('created_at', sa.DateTime(), nullable=True),
    )


def downgrade():
    op.drop_table('guest_comment')
    with op.batch_alter_table('event', schema=None) as batch_op:
        batch_op.drop_column('accent_colour_2')
        batch_op.drop_column('video_note')
        batch_op.drop_column('programme')
        batch_op.drop_column('whatsapp_group')
        batch_op.drop_column('hashtag')
        batch_op.drop_column('greeting_lang')
        batch_op.drop_column('spotify_url')
