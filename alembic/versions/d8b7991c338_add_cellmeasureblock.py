"""add CellMeasureBlock

Revision ID: d8b7991c338
Revises: 4323e1f1a0b8
Create Date: 2014-05-05 16:19:00.256422

"""

# revision identifiers, used by Alembic.
revision = 'd8b7991c338'
down_revision = '4323e1f1a0b8'

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.mysql import BIGINT as BigInteger


def upgrade():
    op.create_table('cell_measure_block',
                    sa.Column('start_id',
                              BigInteger(unsigned=True)),
                    sa.Column('end_id',
                              BigInteger(unsigned=True)),
                    sa.Column('archive_date', sa.DateTime()),
                    sa.Column('s3_key', sa.String(80)),
                    mysql_engine='InnoDB',
                    mysql_charset='utf8',
                    )
    op.create_index('idx_cmblk_archive_date',
                    'cell_measure_block',
                    ['archive_date'])
    op.create_index('idx_cmblk_s3_key',
                    'cell_measure_block',
                    ['s3_key'])
    op.create_index('idx_cmblk_end_id',
                    'cell_measure_block',
                    ['end_id'])


def downgrade():
    op.drop_table('cell_measure_block')
