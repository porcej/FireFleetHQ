"""Add app_unit (Door #) to apparatus

Revision ID: 002_add_app_unit
Revises: 001_initial_firefleethq
Create Date: 2026-07-18

"""
from alembic import op
import sqlalchemy as sa

revision = '002_add_app_unit'
down_revision = '001_initial_firefleethq'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('apparatus') as batch_op:
        batch_op.add_column(sa.Column('app_unit', sa.String(length=64), nullable=True))
        batch_op.create_index('ix_apparatus_app_unit', ['app_unit'])


def downgrade():
    with op.batch_alter_table('apparatus') as batch_op:
        batch_op.drop_index('ix_apparatus_app_unit')
        batch_op.drop_column('app_unit')
