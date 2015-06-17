"""remove content model id columns

Revision ID: 2e0e620ebc92
Revises: 55db289fa497
Create Date: 2015-06-17 12:09:45.022348
"""

import logging

from alembic import op
import sqlalchemy as sa


log = logging.getLogger('alembic.migration')
revision = '2e0e620ebc92'
down_revision = '55db289fa497'


def upgrade():
    for table in ('score', 'stat'):
        stmt = "ALTER TABLE {table} DROP COLUMN `id`".format(table=table)
        op.execute(sa.text(stmt))


def downgrade():
    pass
