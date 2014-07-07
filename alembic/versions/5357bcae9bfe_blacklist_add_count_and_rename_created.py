"""blacklist add count and rename created

Revision ID: 5357bcae9bfe
Revises: 383a10fbb4c8
Create Date: 2014-06-26 12:03:50.659519

"""

# revision identifiers, used by Alembic.
revision = '5357bcae9bfe'
down_revision = '383a10fbb4c8'

from alembic import op
from sqlalchemy.dialects.mysql import INTEGER as Integer
from sqlalchemy import (
    Column,
)
from ichnaea.sa_types import TZDateTime as DateTime


def upgrade():
    op.alter_column('cell_blacklist', 'created', new_column_name='time', existing_type=DateTime())
    op.alter_column('wifi_blacklist', 'created', new_column_name='time', existing_type=DateTime())
    op.add_column('cell_blacklist', Column('count', Integer()))
    op.add_column('wifi_blacklist', Column('count', Integer()))
    op.execute("UPDATE cell_blacklist SET count = 1 WHERE count IS NULL")
    op.execute("UPDATE wifi_blacklist SET count = 1 WHERE count IS NULL")


def downgrade():
    op.alter_column('cell_blacklist', 'time', new_column_name='created')
    op.alter_column('wifi_blacklist', 'time', new_column_name='created')
    op.drop_column('cell_blacklist', 'count')
    op.drop_column('wifi_blacklist', 'count')
