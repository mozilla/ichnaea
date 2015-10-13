"""Rename to radius/samples.

Revision ID: 2c709f81a660
Revises: 33d0f7fb4da0
Create Date: 2015-10-13 14:43:06.587773
"""

import logging

from alembic import op
import sqlalchemy as sa


log = logging.getLogger('alembic.migration')
revision = '2c709f81a660'
down_revision = '33d0f7fb4da0'


def upgrade():
    stmt = ('ALTER TABLE cell '
            'CHANGE COLUMN `range` `radius` int(11), '
            'CHANGE COLUMN `total_measures` `samples` int(10) unsigned')
    log.info('Modify cell table.')
    op.execute(sa.text(stmt))

    stmt = ('ALTER TABLE cell_area '
            'CHANGE COLUMN `range` `radius` int(11), '
            'CHANGE COLUMN `avg_cell_range` `avg_cell_radius` int(11)')
    log.info('Modify cell_area table.')
    op.execute(sa.text(stmt))


def downgrade():
    stmt = ('ALTER TABLE cell '
            'CHANGE COLUMN `radius` `range` int(11), '
            'CHANGE COLUMN `samples` `total_measures` int(10) unsigned')
    log.info('Modify cell table.')
    op.execute(sa.text(stmt))

    stmt = ('ALTER TABLE cell_area '
            'CHANGE COLUMN `radius` `range` int(11), '
            'CHANGE COLUMN `avg_cell_radius` `avg_cell_range` int(11)')
    log.info('Modify cell_area table.')
    op.execute(sa.text(stmt))
