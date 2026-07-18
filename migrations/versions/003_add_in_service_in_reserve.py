"""Add in_service and in_reserve to apparatus

Revision ID: 003_add_in_service_in_reserve
Revises: 002_add_app_unit
Create Date: 2026-07-18

"""
from alembic import op
import sqlalchemy as sa

revision = '003_add_in_service_in_reserve'
down_revision = '002_add_app_unit'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('apparatus') as batch_op:
        batch_op.add_column(sa.Column('in_service', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('in_reserve', sa.Integer(), nullable=True))
        batch_op.create_index('ix_apparatus_in_service', ['in_service'])
        batch_op.create_index('ix_apparatus_in_reserve', ['in_reserve'])
        batch_op.create_index('ix_apparatus_vehicle_type', ['vehicle_type'])


def downgrade():
    with op.batch_alter_table('apparatus') as batch_op:
        batch_op.drop_index('ix_apparatus_vehicle_type')
        batch_op.drop_index('ix_apparatus_in_reserve')
        batch_op.drop_index('ix_apparatus_in_service')
        batch_op.drop_column('in_reserve')
        batch_op.drop_column('in_service')
