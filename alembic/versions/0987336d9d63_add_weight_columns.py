"""Add weight and last_seen columns to station tables.

Revision ID: 0987336d9d63
Revises: 44e1b53944ee
Create Date: 2016-01-26 14:53:32.185623
"""

import logging

from alembic import op
import sqlalchemy as sa


log = logging.getLogger('alembic.migration')
revision = '0987336d9d63'
down_revision = '44e1b53944ee'

TABLES = (['cell_ocid', 'cell_gsm', 'cell_wcdma', 'cell_lte'] +
          ['wifi_shard_%x' % i for i in range(16)])

AREA_TABLES = ('cell_area', 'cell_area_ocid')


def upgrade():
    for table in TABLES:
        log.info('Add weight and last_seen columns to table: %s', table)
        stmt = ('ALTER TABLE {table} '
                'ADD COLUMN `weight` DOUBLE DEFAULT NULL AFTER `source`, '
                'ADD COLUMN `last_seen` DATE DEFAULT NULL')
        op.execute(sa.text(stmt.format(table=table)))

        log.info('Fill weight column with values')
        stmt = ('UPDATE {table} SET weight = samples')
        op.execute(sa.text(stmt.format(table=table)))

    for table in AREA_TABLES:
        log.info('Add last_seen column to table: %s', table)
        stmt = ('ALTER TABLE {table} '
                'ADD COLUMN `last_seen` DATE DEFAULT NULL AFTER `num_cells`')
        op.execute(sa.text(stmt.format(table=table)))


def downgrade():
    for table in TABLES:
        log.info('Drop weight and last_seen columns from table: %s', table)
        stmt = ('ALTER TABLE {table} '
                'DROP COLUMN `weight`, DROP COLUMN `last_seen`')
        op.execute(sa.text(stmt.format(table=table)))

    for table in AREA_TABLES:
        log.info('Drop last_seen column from table: %s', table)
        stmt = ('ALTER TABLE {table} DROP COLUMN `last_seen`')
        op.execute(sa.text(stmt.format(table=table)))
