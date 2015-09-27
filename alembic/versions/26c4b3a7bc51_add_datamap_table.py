"""add datamap table

Revision ID: 26c4b3a7bc51
Revises: 47ed7a40413b
Create Date: 2015-09-27 12:11:05.040120
"""

import logging

from alembic import op
import sqlalchemy as sa


log = logging.getLogger('alembic.migration')
revision = '26c4b3a7bc51'
down_revision = '47ed7a40413b'


def upgrade():
    log.info('Add datamap table.')
    stmt = '''\
CREATE TABLE `datamap` (
`grid` binary(8) NOT NULL,
`created` date DEFAULT NULL,
`modified` date DEFAULT NULL,
PRIMARY KEY (`grid`),
KEY `idx_datamap_created` (`created`),
KEY `idx_datamap_modified` (`modified`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8
'''
    op.execute(sa.text(stmt))


def downgrade():
    pass
