"""remove old cell tables

Revision ID: 44e1b53944ee
Revises: 9743e7b8a17a
Create Date: 2016-01-12 16:16:44.633093
"""

import logging

from alembic import op
import sqlalchemy as sa


log = logging.getLogger('alembic.migration')
revision = '44e1b53944ee'
down_revision = '9743e7b8a17a'


def upgrade():
    stmt = 'DROP TABLE {table}'
    for table in ('cell', 'cell_blacklist'):
        log.info('Drop table: %s', table)
        op.execute(sa.text(stmt.format(table=table)))


def downgrade():
    pass
