"""Add pstrax_alert table and last_alerts_scrape

Revision ID: 004_pstrax_alerts
Revises: 003_add_in_service_in_reserve
Create Date: 2026-07-18

"""
from alembic import op
import sqlalchemy as sa

revision = '004_pstrax_alerts'
down_revision = '003_add_in_service_in_reserve'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'pstrax_alert',
        sa.Column('alert_id', sa.Integer(), nullable=False),
        sa.Column('alert_date', sa.String(length=64), nullable=True),
        sa.Column('category', sa.String(length=128), nullable=True),
        sa.Column('app_name', sa.String(length=255), nullable=True),
        sa.Column('post_station', sa.String(length=128), nullable=True),
        sa.Column('current_location', sa.String(length=128), nullable=True),
        sa.Column('alert_text', sa.Text(), nullable=True),
        sa.Column('alert_text_raw', sa.Text(), nullable=True),
        sa.Column('opened_by', sa.String(length=128), nullable=True),
        sa.Column('priority', sa.String(length=64), nullable=True),
        sa.Column('last_update', sa.String(length=64), nullable=True),
        sa.Column('with_image', sa.Integer(), nullable=True),
        sa.Column('cost', sa.String(length=64), nullable=True),
        sa.Column('raw_json', sa.Text(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('alert_id'),
    )
    op.create_index('ix_pstrax_alert_alert_date', 'pstrax_alert', ['alert_date'])
    op.create_index('ix_pstrax_alert_category', 'pstrax_alert', ['category'])
    op.create_index('ix_pstrax_alert_app_name', 'pstrax_alert', ['app_name'])
    op.create_index('ix_pstrax_alert_post_station', 'pstrax_alert', ['post_station'])
    op.create_index('ix_pstrax_alert_priority', 'pstrax_alert', ['priority'])

    with op.batch_alter_table('scrape_config') as batch_op:
        batch_op.add_column(sa.Column('last_alerts_scrape', sa.DateTime(), nullable=True))


def downgrade():
    with op.batch_alter_table('scrape_config') as batch_op:
        batch_op.drop_column('last_alerts_scrape')
    op.drop_index('ix_pstrax_alert_priority', table_name='pstrax_alert')
    op.drop_index('ix_pstrax_alert_post_station', table_name='pstrax_alert')
    op.drop_index('ix_pstrax_alert_app_name', table_name='pstrax_alert')
    op.drop_index('ix_pstrax_alert_category', table_name='pstrax_alert')
    op.drop_index('ix_pstrax_alert_alert_date', table_name='pstrax_alert')
    op.drop_table('pstrax_alert')
