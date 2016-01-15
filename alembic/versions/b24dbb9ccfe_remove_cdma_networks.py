"""Remove CDMA networks.

Revision ID: b24dbb9ccfe
Revises: None
Create Date: 2015-09-16 11:50:38.367525
"""

import logging

from alembic import op
import sqlalchemy as sa


log = logging.getLogger('alembic.migration')
revision = 'b24dbb9ccfe'
down_revision = None


def upgrade():
    stmt = 'DELETE FROM {table} WHERE `radio` = 1'
    for table in ('cell', 'cell_area', 'ocid_cell', 'ocid_cell_area'):
        log.info('Remove CDMA networks from %s table', table)
        op.execute(sa.text(stmt.format(table=table)))


def downgrade():
    pass
