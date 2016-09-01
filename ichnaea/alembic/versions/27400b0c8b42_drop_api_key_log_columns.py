"""drop api_key log columns

Revision ID: 27400b0c8b42
Revises: 88d1704f1aef
Create Date: 2016-04-06 19:36:10.180072
"""

import logging

from alembic import op
import sqlalchemy as sa


log = logging.getLogger('alembic.migration')
revision = '27400b0c8b42'
down_revision = '88d1704f1aef'


def upgrade():
    log.info('Drop log columns from api_key table.')
    stmt = '''\
ALTER TABLE api_key
DROP COLUMN `log_locate`,
DROP COLUMN `log_region`,
DROP COLUMN `log_submit`
'''
    op.execute(sa.text(stmt))


def downgrade():
    log.info('Add log columns to api_key table.')
    stmt = '''\
ALTER TABLE api_key
ADD COLUMN `log_locate` TINYINT(1) DEFAULT NULL,
ADD COLUMN `log_region` TINYINT(1) DEFAULT NULL,
ADD COLUMN `log_submit` TINYINT(1) DEFAULT NULL
'''
    op.execute(sa.text(stmt))
