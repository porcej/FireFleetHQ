"""Rename apparatus sync interval from hours to minutes (default 15)

Revision ID: 006_apparatus_interval_minutes
Revises: 005_add_reserve_homes
Create Date: 2026-07-19

"""
from alembic import op
import sqlalchemy as sa

revision = '006_apparatus_interval_minutes'
down_revision = '005_add_reserve_homes'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('scrape_config') as batch_op:
        batch_op.add_column(
            sa.Column(
                'apparatus_scrape_interval_minutes',
                sa.Integer(),
                nullable=False,
                server_default='15',
            )
        )

    connection = op.get_bind()
    connection.execute(
        sa.text(
            """
            UPDATE scrape_config
            SET apparatus_scrape_interval_minutes = CASE
                WHEN apparatus_scrape_interval_hours IS NULL
                     OR apparatus_scrape_interval_hours < 1 THEN 15
                WHEN apparatus_scrape_interval_hours = 24 THEN 15
                ELSE apparatus_scrape_interval_hours * 60
            END
            """
        )
    )

    with op.batch_alter_table('scrape_config') as batch_op:
        batch_op.drop_column('apparatus_scrape_interval_hours')


def downgrade():
    with op.batch_alter_table('scrape_config') as batch_op:
        batch_op.add_column(
            sa.Column(
                'apparatus_scrape_interval_hours',
                sa.Integer(),
                nullable=False,
                server_default='24',
            )
        )

    connection = op.get_bind()
    connection.execute(
        sa.text(
            """
            UPDATE scrape_config
            SET apparatus_scrape_interval_hours = CASE
                WHEN apparatus_scrape_interval_minutes IS NULL
                     OR apparatus_scrape_interval_minutes < 1 THEN 24
                ELSE MAX(1, (apparatus_scrape_interval_minutes + 59) / 60)
            END
            """
        )
    )

    with op.batch_alter_table('scrape_config') as batch_op:
        batch_op.drop_column('apparatus_scrape_interval_minutes')
