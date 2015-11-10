"""drop mapstat table

Revision ID: 91fb41d12c5
Revises: 78e6322b4d9
Create Date: 2015-11-10 16:00:04.261758
"""

import logging

from alembic import op


log = logging.getLogger('alembic.migration')
revision = '91fb41d12c5'
down_revision = '78e6322b4d9'


def upgrade():
    log.info('Drop mapstat table.')
    op.drop_table('mapstat')


def downgrade():
    pass
