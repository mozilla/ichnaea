"""Drop api_key log column.

Revision ID: 3fd11bfaca02
Revises: 583a68296584
Create Date: 2015-10-13 15:20:39.425076
"""

import logging

from alembic import op
import sqlalchemy as sa


log = logging.getLogger('alembic.migration')
revision = '3fd11bfaca02'
down_revision = '583a68296584'


def upgrade():
    log.info('Drop api_key log column.')
    stmt = "ALTER TABLE api_key DROP COLUMN `log`"
    op.execute(sa.text(stmt))


def downgrade():
    pass
