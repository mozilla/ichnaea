"""add MeasureBlock

Revision ID: 4323e1f1a0b8
Revises: 51ba8090058d
Create Date: 2014-05-05 13:43:43.004457

"""

# revision identifiers, used by Alembic.
revision = '4323e1f1a0b8'
down_revision = '51ba8090058d'

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.mysql import BIGINT as BigInteger


def upgrade():
    op.create_table('measure_block',
                    sa.Column('id',
                              BigInteger(unsigned=True),
                              primary_key=True,
                              autoincrement=True),
                    sa.Column('measure_type', sa.SmallInteger()),
                    sa.Column('s3_key', sa.String(80)),
                    sa.Column('archive_date', sa.DateTime()),
                    sa.Column('archive_sha', sa.BINARY(length=20)),
                    sa.Column('start_id', BigInteger(unsigned=True)),
                    sa.Column('end_id', BigInteger(unsigned=True)),
                    mysql_engine='InnoDB',
                    mysql_charset='utf8',
                    mysql_row_format='compressed',
                    mysql_key_block_size='4',
                    )
    op.create_index('idx_measure_block_archive_date',
                    'measure_block',
                    ['archive_date'])
    op.create_index('idx_measure_block_s3_key',
                    'measure_block',
                    ['s3_key'])
    op.create_index('idx_measure_block_end_id',
                    'measure_block',
                    ['end_id'])


def downgrade():
    op.drop_table('measure_block')
