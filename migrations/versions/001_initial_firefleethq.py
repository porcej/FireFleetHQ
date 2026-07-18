"""Initial FireFleetHQ schema

Revision ID: 001_initial_firefleethq
Revises:
Create Date: 2026-07-18

"""
from alembic import op
import sqlalchemy as sa

revision = '001_initial_firefleethq'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'user',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('username', sa.String(length=80), nullable=False),
        sa.Column('password_hash', sa.String(length=255), nullable=False),
        sa.Column('is_admin', sa.Boolean(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('username'),
    )
    op.create_table(
        'task',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('completed', sa.Boolean(), nullable=True),
        sa.Column('priority', sa.Integer(), nullable=True),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['user.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_table(
        'alert',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('message', sa.Text(), nullable=False),
        sa.Column('start_time', sa.DateTime(), nullable=True),
        sa.Column('end_time', sa.DateTime(), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=True),
        sa.Column('created_by', sa.Integer(), nullable=False),
        sa.Column('color_theme', sa.String(length=20), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['created_by'], ['user.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_table(
        'scrape_config',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('pstrax_base_url', sa.String(length=255), nullable=False),
        sa.Column('pstrax_username', sa.String(length=255), nullable=True),
        sa.Column('pstrax_password_encrypted', sa.Text(), nullable=True),
        sa.Column('last_scrape', sa.DateTime(), nullable=True),
        sa.Column('scrape_interval', sa.Integer(), nullable=True),
        sa.Column('apparatus_scrape_interval_hours', sa.Integer(), nullable=False),
        sa.Column('last_apparatus_scrape', sa.DateTime(), nullable=True),
        sa.Column('default_alert_color', sa.String(length=20), nullable=False),
        sa.Column('alerts_font_size', sa.Integer(), nullable=False),
        sa.Column('apparatus_statuses', sa.String(length=255), nullable=False),
        sa.Column('apparatus_stations', sa.String(length=512), nullable=False),
        sa.Column('app_timezone', sa.String(length=64), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_table(
        'scrape_data',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('data', sa.Text(), nullable=False),
        sa.Column('scraped_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_scrape_data_scraped_at', 'scrape_data', ['scraped_at'])
    op.create_table(
        'apparatus',
        sa.Column('vehicle_id', sa.Integer(), nullable=False),
        sa.Column('unit_name', sa.String(length=128), nullable=True),
        sa.Column('station', sa.String(length=128), nullable=True),
        sa.Column('vehicle_type', sa.String(length=128), nullable=True),
        sa.Column('status', sa.String(length=64), nullable=True),
        sa.Column('status_class', sa.String(length=128), nullable=True),
        sa.Column('status_display_raw', sa.Text(), nullable=True),
        sa.Column('open_alerts', sa.Integer(), nullable=True),
        sa.Column('open_alerts_display', sa.Text(), nullable=True),
        sa.Column('checks_due', sa.Integer(), nullable=True),
        sa.Column('checks_due_display', sa.Text(), nullable=True),
        sa.Column('scba_due', sa.Integer(), nullable=True),
        sa.Column('assets_due', sa.Integer(), nullable=True),
        sa.Column('supplies_due', sa.Integer(), nullable=True),
        sa.Column('next_due', sa.String(length=20), nullable=True),
        sa.Column('next_due_display', sa.Text(), nullable=True),
        sa.Column('next_due_class', sa.String(length=128), nullable=True),
        sa.Column('raw_json', sa.Text(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('vehicle_id'),
    )
    op.create_index('ix_apparatus_unit_name', 'apparatus', ['unit_name'])
    op.create_index('ix_apparatus_station', 'apparatus', ['station'])
    op.create_index('ix_apparatus_status', 'apparatus', ['status'])
    op.create_index('ix_apparatus_next_due', 'apparatus', ['next_due'])


def downgrade():
    op.drop_index('ix_apparatus_next_due', table_name='apparatus')
    op.drop_index('ix_apparatus_status', table_name='apparatus')
    op.drop_index('ix_apparatus_station', table_name='apparatus')
    op.drop_index('ix_apparatus_unit_name', table_name='apparatus')
    op.drop_table('apparatus')
    op.drop_index('ix_scrape_data_scraped_at', table_name='scrape_data')
    op.drop_table('scrape_data')
    op.drop_table('scrape_config')
    op.drop_table('alert')
    op.drop_table('task')
    op.drop_table('user')
