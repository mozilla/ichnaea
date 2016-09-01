"""fallback config

Revision ID: fdd0b256cecc
Revises: 4b11500c9014
Create Date: 2016-03-30 17:44:01.349983
"""

import logging

from alembic import op
import sqlalchemy as sa


log = logging.getLogger('alembic.migration')
revision = 'fdd0b256cecc'
down_revision = '4b11500c9014'


def upgrade():
    log.info('Add fallback options to api_key table.')
    stmt = '''\
ALTER TABLE api_key
ADD COLUMN `fallback_name` VARCHAR(40) DEFAULT NULL,
ADD COLUMN `fallback_url` VARCHAR(256) DEFAULT NULL,
ADD COLUMN `fallback_ratelimit` INT(11) DEFAULT NULL,
ADD COLUMN `fallback_ratelimit_interval` INT(11) DEFAULT NULL,
ADD COLUMN `fallback_cache_expire` INT(11) DEFAULT NULL
'''
    op.execute(sa.text(stmt))


def downgrade():
    log.info('Drop fallback options from api_key table.')
    stmt = '''\
ALTER TABLE api_key
DROP COLUMN `fallback_name`,
DROP COLUMN `fallback_url`,
DROP COLUMN `fallback_ratelimit`,
DROP COLUMN `fallback_ratelimit_interval`,
DROP COLUMN `fallback_cache_expire`
'''
    op.execute(sa.text(stmt))
