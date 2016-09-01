"""drop cell_ocid table

Revision ID: 88d1704f1aef
Revises: e23ba53ab89b
Create Date: 2016-04-06 19:28:54.467805
"""

import logging

from alembic import op
import sqlalchemy as sa


log = logging.getLogger('alembic.migration')
revision = '88d1704f1aef'
down_revision = 'e23ba53ab89b'


def upgrade():
    log.info('Drop cell_ocid table.')
    stmt = 'DROP TABLE cell_ocid'
    op.execute(sa.text(stmt))


def downgrade():
    log.info('Recreate cell_ocid table.')
    stmt = '''\
CREATE TABLE `cell_ocid` (
  `max_lat` double DEFAULT NULL,
  `min_lat` double DEFAULT NULL,
  `max_lon` double DEFAULT NULL,
  `min_lon` double DEFAULT NULL,
  `lat` double DEFAULT NULL,
  `lon` double DEFAULT NULL,
  `created` datetime DEFAULT NULL,
  `modified` datetime DEFAULT NULL,
  `radius` int(10) unsigned DEFAULT NULL,
  `region` varchar(2) DEFAULT NULL,
  `samples` int(10) unsigned DEFAULT NULL,
  `source` tinyint(4) DEFAULT NULL,
  `weight` double DEFAULT NULL,
  `last_seen` date DEFAULT NULL,
  `block_first` date DEFAULT NULL,
  `block_last` date DEFAULT NULL,
  `block_count` tinyint(3) unsigned DEFAULT NULL,
  `cellid` binary(11) NOT NULL,
  `radio` tinyint(4) NOT NULL,
  `mcc` smallint(6) NOT NULL,
  `mnc` smallint(6) NOT NULL,
  `lac` smallint(5) unsigned NOT NULL,
  `cid` int(10) unsigned NOT NULL,
  `psc` smallint(6) DEFAULT NULL,
  PRIMARY KEY (`cellid`),
  UNIQUE KEY `cell_ocid_cellid_unique` (`radio`,`mcc`,`mnc`,`lac`,`cid`),
  KEY `cell_ocid_region_radio_idx` (`region`,`radio`),
  KEY `cell_ocid_created_idx` (`created`),
  KEY `cell_ocid_modified_idx` (`modified`),
  KEY `cell_ocid_latlon_idx` (`lat`,`lon`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8
'''
    op.execute(sa.text(stmt))
