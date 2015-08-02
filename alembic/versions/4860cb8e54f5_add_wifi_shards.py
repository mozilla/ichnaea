"""add wifi shards

Revision ID: 4860cb8e54f5
Revises: 1a320a751cf
Create Date: 2015-08-02 17:24:14.293552
"""

import logging

from alembic import op
import sqlalchemy as sa


log = logging.getLogger('alembic.migration')
revision = '4860cb8e54f5'
down_revision = '1a320a751cf'


def upgrade():
    log.info('Create wifi_shard_* tables')
    stmt = """\
CREATE TABLE `wifi_shard_{id}` (
`mac` binary(6) NOT NULL,
`lat` double DEFAULT NULL,
`lon` double DEFAULT NULL,
`radius` int(10) unsigned DEFAULT NULL,
`max_lat` double DEFAULT NULL,
`min_lat` double DEFAULT NULL,
`max_lon` double DEFAULT NULL,
`min_lon` double DEFAULT NULL,
`country` varchar(2) DEFAULT NULL,
`samples` int(10) unsigned DEFAULT NULL,
`source` tinyint(4) DEFAULT NULL,
`created` datetime DEFAULT NULL,
`modified` datetime DEFAULT NULL,
`block_first` date DEFAULT NULL,
`block_last` date DEFAULT NULL,
`block_count` tinyint(3) unsigned DEFAULT NULL,
PRIMARY KEY (`mac`),
KEY `wifi_shard_{id}_country_idx` (`country`),
KEY `wifi_shard_{id}_created_idx` (`created`),
KEY `wifi_shard_{id}_modified_idx` (`modified`),
KEY `wifi_shard_{id}_latlon_idx` (`lat`, `lon`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8
"""
    shard_ids = (
        '0', '1', '2', '3', '4', '5', '6', '7',
        '8', '9', 'a', 'b', 'c', 'd', 'e', 'f',
    )
    for shard_id in shard_ids:
        op.execute(sa.text(stmt.format(id=shard_id)))


def downgrade():
    pass
