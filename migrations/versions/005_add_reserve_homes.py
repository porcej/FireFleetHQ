"""Add reserve_homes to scrape_config

Revision ID: 005_add_reserve_homes
Revises: 004_pstrax_alerts
Create Date: 2026-07-18

"""
from alembic import op
import sqlalchemy as sa

revision = '005_add_reserve_homes'
down_revision = '004_pstrax_alerts'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('scrape_config') as batch_op:
        batch_op.add_column(
            sa.Column('reserve_homes', sa.String(length=512), nullable=False, server_default='')
        )


def downgrade():
    with op.batch_alter_table('scrape_config') as batch_op:
        batch_op.drop_column('reserve_homes')
