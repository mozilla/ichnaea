"""remove observation tables

Revision ID: 1a320a751cf
Revises: 2e0e620ebc92
Create Date: 2015-07-15 14:37:50.410310
"""

import logging

from alembic import op


log = logging.getLogger('alembic.migration')
revision = '1a320a751cf'
down_revision = '2e0e620ebc92'


def upgrade():
    log.info('Drop cell_measure table')
    op.drop_table('cell_measure')
    log.info('Drop wifi_measure table')
    op.drop_table('wifi_measure')


def downgrade():
    pass
