"""api_key detailed log

Revision ID: 33d0f7fb4da0
Revises: 460ce3d4fe09
Create Date: 2015-10-13 11:35:57.104666
"""

import logging

from alembic import op
import sqlalchemy as sa


log = logging.getLogger('alembic.migration')
revision = '33d0f7fb4da0'
down_revision = '460ce3d4fe09'


def upgrade():
    log.info('Add log columns to table api_key.')
    stmt = ('ALTER TABLE api_key '
            'ADD COLUMN `log_locate` TINYINT(1) AFTER `log`, '
            'ADD COLUMN `log_region` TINYINT(1) AFTER `log_locate`, '
            'ADD COLUMN `log_submit` TINYINT(1) AFTER `log_region`')
    op.execute(sa.text(stmt))
    stmt = ('UPDATE api_key SET log_locate = log, '
            'log_region = 0, log_submit = log')
    op.execute(sa.text(stmt))


def downgrade():
    pass
