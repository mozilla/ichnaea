"""Add sharded Bluetooth tables.

Revision ID: b247526b9501
Revises: 0987336d9d63
Create Date: 2016-01-26 21:36:55.104109
"""

import logging

from alembic import op
import sqlalchemy as sa


log = logging.getLogger('alembic.migration')
revision = 'b247526b9501'
down_revision = '0987336d9d63'


def upgrade():
    log.info('Create blue_shard_* tables')
    stmt = """\
CREATE TABLE `blue_shard_{id}` (
`mac` binary(6) NOT NULL,
`lat` double DEFAULT NULL,
`lon` double DEFAULT NULL,
`radius` int(10) unsigned DEFAULT NULL,
`max_lat` double DEFAULT NULL,
`min_lat` double DEFAULT NULL,
`max_lon` double DEFAULT NULL,
`min_lon` double DEFAULT NULL,
`created` datetime DEFAULT NULL,
`modified` datetime DEFAULT NULL,
`region` varchar(2) DEFAULT NULL,
`samples` int(10) unsigned DEFAULT NULL,
`source` tinyint(4) DEFAULT NULL,
`weight` double DEFAULT NULL,
`last_seen` date DEFAULT NULL,
`block_first` date DEFAULT NULL,
`block_last` date DEFAULT NULL,
`block_count` tinyint(3) unsigned DEFAULT NULL,
PRIMARY KEY (`mac`),
KEY `blue_shard_{id}_region_idx` (`region`),
KEY `blue_shard_{id}_created_idx` (`created`),
KEY `blue_shard_{id}_modified_idx` (`modified`),
KEY `blue_shard_{id}_latlon_idx` (`lat`, `lon`)
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
