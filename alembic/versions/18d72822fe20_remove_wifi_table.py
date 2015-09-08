"""Remove wifi table.

Revision ID: 18d72822fe20
Revises: c1efc747c9
Create Date: 2015-09-08 12:28:53.383126
"""

import logging

from alembic import op


log = logging.getLogger('alembic.migration')
revision = '18d72822fe20'
down_revision = 'c1efc747c9'


def upgrade():
    log.info('Drop wifi table')
    op.drop_table('wifi')


def downgrade():
    pass
