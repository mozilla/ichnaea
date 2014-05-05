"""add cellmeasure checkpoint

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
    op.create_table('cell_measure_checkpoint',
                    sa.Column('cell_measure_id',
                        BigInteger(unsigned=True),
                        primary_key=True),
                    mysql_engine='InnoDB',
                    mysql_charset='utf8',
                    )


def downgrade():
    op.drop_table('cell_measure_checkpoint')
