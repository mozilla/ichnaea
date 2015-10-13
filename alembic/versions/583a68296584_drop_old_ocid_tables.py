"""Drop old OCID tables.

Revision ID: 583a68296584
Revises: 2c709f81a660
Create Date: 2015-10-13 15:12:44.745660
"""

import logging

from alembic import op


log = logging.getLogger('alembic.migration')
revision = '583a68296584'
down_revision = '2c709f81a660'


def upgrade():
    log.info('Drop ocid_cell_area table')
    op.drop_table('ocid_cell_area')

    log.info('Drop ocid_cell table')
    op.drop_table('ocid_cell')


def downgrade():
    pass
