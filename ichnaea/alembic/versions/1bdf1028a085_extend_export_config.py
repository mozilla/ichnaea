"""extend export config

Revision ID: 1bdf1028a085
Revises: 000000000000
Create Date: 2016-04-14 14:08:27.104535
"""

import logging

from alembic import op
import sqlalchemy as sa


log = logging.getLogger('alembic.migration')
revision = '1bdf1028a085'
down_revision = '000000000000'


def upgrade():
    log.info('Add skip_sources column to export_config table.')
    stmt = '''\
ALTER TABLE export_config
ADD COLUMN `skip_sources` varchar(64) DEFAULT NULL
'''
    op.execute(sa.text(stmt))


def downgrade():
    log.info('Drop skip_sources column from export_config table.')
    stmt = '''\
ALTER TABLE export_config
DROP COLUMN `skip_sources`
'''
    op.execute(sa.text(stmt))
