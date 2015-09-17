"""Add cell area id columns.

Revision ID: 47ed7a40413b
Revises: b24dbb9ccfe
Create Date: 2015-09-17 13:20:01.952124
"""

import logging

from alembic import op
import sqlalchemy as sa


log = logging.getLogger('alembic.migration')
revision = '47ed7a40413b'
down_revision = 'b24dbb9ccfe'


def upgrade():
    for table in ('cell_area', 'ocid_cell_area'):
        log.info('Add areaid column to table: %s', table)
        stmt = 'ALTER TABLE {table} ADD COLUMN `areaid` BINARY(7) AFTER `lac`'
        op.execute(sa.text(stmt.format(table=table)))

        log.info('Fill areaid column with values')
        stmt = ('UPDATE {table} SET areaid = UNHEX(CONCAT('
                'LPAD(HEX(`radio`), 2, 0), LPAD(HEX(`mcc`), 4, 0), '
                'LPAD(HEX(`mnc`), 4, 0), LPAD(HEX(`lac`), 4, 0)))')
        op.execute(sa.text(stmt.format(table=table)))

        log.info('Add unique constraint to areaid column')
        stmt = ('ALTER TABLE {table} '
                'MODIFY COLUMN areaid BINARY(7) NOT NULL, '
                'ADD UNIQUE `{table}_areaid_unique` (`areaid`)')
        op.execute(sa.text(stmt.format(table=table)))


def downgrade():
    pass
