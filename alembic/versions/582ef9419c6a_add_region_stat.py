"""add region stat

Revision ID: 582ef9419c6a
Revises: 238aca86fe8d
Create Date: 2015-10-13 18:58:43.912672
"""

import logging

from alembic import op
import sqlalchemy as sa


log = logging.getLogger('alembic.migration')
revision = '582ef9419c6a'
down_revision = '238aca86fe8d'


def upgrade():
    stmt = '''\
CREATE TABLE `region_stat` (
`region` varchar(2) NOT NULL,
`gsm` int(10) unsigned DEFAULT NULL,
`wcdma` int(10) unsigned DEFAULT NULL,
`lte` int(10) unsigned DEFAULT NULL,
`wifi` bigint(20) unsigned DEFAULT NULL,
PRIMARY KEY (`region`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8'''
    log.info('Add region_stat table.')
    op.execute(sa.text(stmt))


def downgrade():
    log.info('Drop region_stat table.')
    op.drop_table('region_stat')
