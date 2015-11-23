"""Add cell shards.

Revision ID: 40d609897296
Revises: 91fb41d12c5
Create Date: 2015-11-23 12:16:46.547983
"""

import logging

from alembic import op
import sqlalchemy as sa


log = logging.getLogger('alembic.migration')
revision = '40d609897296'
down_revision = '91fb41d12c5'


def upgrade():
    stmt = '''\
CREATE TABLE `cell_{id}` (
  `cellid` binary(11) NOT NULL,
  `radio` tinyint(4) NOT NULL,
  `mcc` smallint(6) NOT NULL,
  `mnc` smallint(6) NOT NULL,
  `lac` smallint(5) unsigned NOT NULL,
  `cid` int(10) unsigned NOT NULL,
  `psc` smallint(6) DEFAULT NULL,
  `lat` double DEFAULT NULL,
  `lon` double DEFAULT NULL,
  `radius` int(10) unsigned DEFAULT NULL,
  `max_lat` double DEFAULT NULL,
  `min_lat` double DEFAULT NULL,
  `max_lon` double DEFAULT NULL,
  `min_lon` double DEFAULT NULL,
  `region` varchar(2) DEFAULT NULL,
  `samples` int(10) unsigned DEFAULT NULL,
  `source` tinyint(4) DEFAULT NULL,
  `created` datetime DEFAULT NULL,
  `modified` datetime DEFAULT NULL,
  `block_first` date DEFAULT NULL,
  `block_last` date DEFAULT NULL,
  `block_count` tinyint(3) unsigned DEFAULT NULL,
  PRIMARY KEY (`cellid`),
  UNIQUE KEY `cell_{id}_cellid_unique` (`radio`,`mcc`,`mnc`,`lac`,`cid`),
  KEY `cell_{id}_region_idx` (`region`),
  KEY `cell_{id}_created_idx` (`created`),
  KEY `cell_{id}_latlon_idx` (`lat`,`lon`),
  KEY `cell_{id}_modified_idx` (`modified`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8
'''
    shard_ids = ('gsm', 'wcdma', 'lte')
    for shard_id in shard_ids:
        op.execute(sa.text(stmt.format(id=shard_id)))


def downgrade():
    pass
