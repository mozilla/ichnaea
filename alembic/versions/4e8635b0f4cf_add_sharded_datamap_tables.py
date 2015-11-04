"""add sharded datamap tables

Revision ID: 4e8635b0f4cf
Revises: 450f02b5e1ca
Create Date: 2015-11-04 12:07:59.769656
"""

import logging

from alembic import op
import sqlalchemy as sa


log = logging.getLogger('alembic.migration')
revision = '4e8635b0f4cf'
down_revision = '450f02b5e1ca'


def upgrade():
    log.info('Drop non-sharded datamap table.')
    op.drop_table('datamap')

    stmt = '''\
CREATE TABLE `datamap_{id}` (
`grid` binary(8) NOT NULL,
`created` date DEFAULT NULL,
`modified` date DEFAULT NULL,
PRIMARY KEY (`grid`),
KEY `datamap_{id}_created_idx` (`created`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8
'''

    shard_ids = ('ne', 'nw', 'se', 'sw')
    for shard_id in shard_ids:
        log.info('Add datamap_%s table.' % shard_id)
        op.execute(sa.text(stmt.format(id=shard_id)))


def downgrade():
    log.info('Drop sharded datamap tables.')
    op.drop_table('datamap_ne')
    op.drop_table('datamap_nw')
    op.drop_table('datamap_se')
    op.drop_table('datamap_sw')

    log.info('Add non-sharded datamap table.')
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
