"""add export config

Revision ID: 6ec824122610
Revises: 4255b858a37e
Create Date: 2016-04-12 13:14:16.036781
"""

import logging

from alembic import op
import sqlalchemy as sa


log = logging.getLogger('alembic.migration')
revision = '6ec824122610'
down_revision = '4255b858a37e'


def upgrade():
    log.info('Add export_config table.')
    stmt = '''\
CREATE TABLE `export_config` (
  `name` varchar(40) NOT NULL,
  `batch` int(11) DEFAULT NULL,
  `schema` varchar(32) DEFAULT NULL,
  `url` varchar(512) DEFAULT NULL,
  `skip_keys` varchar(1024) DEFAULT NULL,
  PRIMARY KEY (`name`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8
'''
    op.execute(sa.text(stmt))


def downgrade():
    log.info('Drop export_config table.')
    stmt = 'DROP TABLE export_config'
    op.execute(sa.text(stmt))
