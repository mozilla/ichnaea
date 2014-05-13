"""added sha hash to CellMeasureBlock for s3 archive verification

Revision ID: 141ea8944bc3
Revises: d8b7991c338
Create Date: 2014-05-12 11:27:17.218570

"""

# revision identifiers, used by Alembic.
revision = '141ea8944bc3'
down_revision = 'd8b7991c338'

from alembic import op
import sqlalchemy as sa


def upgrade():
    op.add_column('measure_block',
                  sa.Column('archive_sha', sa.String(80)))


def downgrade():
    op.drop_column('measure_block',
                   sa.Column('archive_sha', sa.String(80)))
