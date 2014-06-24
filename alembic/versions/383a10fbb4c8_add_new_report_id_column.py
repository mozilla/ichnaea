"""Add new report_id column

Revision ID: 383a10fbb4c8
Revises: 177fd68744a4
Create Date: 2014-06-24 06:53:32.649938

"""

# revision identifiers, used by Alembic.
revision = '383a10fbb4c8'
down_revision = '177fd68744a4'

from alembic import op
import sqlalchemy as sa


def upgrade():
    stmt = "ALTER TABLE %s ADD COLUMN report_id BINARY(16) AFTER id"
    op.execute(sa.text(stmt % "cell_measure"))
    op.execute(sa.text(stmt % "wifi_measure"))


def downgrade():
    op.drop_column('cell_measure', 'report_id')
    op.drop_column('wifi_measure', 'report_id')
