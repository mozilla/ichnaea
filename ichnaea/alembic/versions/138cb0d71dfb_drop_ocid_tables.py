"""Drop OCID tables

Revision ID: 138cb0d71dfb
Revises: 5797389a3842
Create Date: 2017-08-08 11:15:19.821330
"""

import logging

from alembic import op
import sqlalchemy as sa


log = logging.getLogger('alembic.migration')
revision = '138cb0d71dfb'
down_revision = '5797389a3842'


def upgrade():
    for table in ('cell_area_ocid', 'cell_gsm_ocid',
                  'cell_lte_ocid', 'cell_wcdma_ocid'):
        log.info('Drop %s table.' % table)
        stmt = 'DROP TABLE %s' % table
        op.execute(sa.text(stmt))


def downgrade():
    log.info('Recreate cell_area_ocid table.')
    stmt = '''\
CREATE TABLE `cell_area_ocid` (
  `lat` double DEFAULT NULL,
  `lon` double DEFAULT NULL,
  `created` datetime DEFAULT NULL,
  `modified` datetime DEFAULT NULL,
  `areaid` binary(7) NOT NULL,
  `radio` tinyint(4) NOT NULL,
  `mcc` smallint(6) NOT NULL,
  `mnc` smallint(6) NOT NULL,
  `lac` smallint(5) unsigned NOT NULL,
  `radius` int(11) DEFAULT NULL,
  `region` varchar(2) DEFAULT NULL,
  `avg_cell_radius` int(10) unsigned DEFAULT NULL,
  `num_cells` int(10) unsigned DEFAULT NULL,
  `last_seen` date DEFAULT NULL,
  PRIMARY KEY (`areaid`),
  UNIQUE KEY `cell_area_ocid_areaid_unique` (`radio`,`mcc`,`mnc`,`lac`),
  KEY `cell_area_ocid_latlon_idx` (`lat`,`lon`),
  KEY `cell_area_ocid_region_radio_idx` (`region`,`radio`),
  KEY `cell_area_ocid_created_idx` (`created`),
  KEY `cell_area_ocid_modified_idx` (`modified`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8
'''
    op.execute(sa.text(stmt))

    log.info('Recreate cell_gsm_ocid table.')
    stmt = '''\
CREATE TABLE `cell_gsm_ocid` (
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
  UNIQUE KEY `cell_gsm_ocid_cellid_unique` (`radio`,`mcc`,`mnc`,`lac`,`cid`),
  KEY `cell_gsm_ocid_region_idx` (`region`),
  KEY `cell_gsm_ocid_latlon_idx` (`lat`,`lon`),
  KEY `cell_gsm_ocid_modified_idx` (`modified`),
  KEY `cell_gsm_ocid_created_idx` (`created`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8
'''
    op.execute(sa.text(stmt))

    log.info('Recreate cell_lte_ocid table.')
    stmt = '''\
CREATE TABLE `cell_lte_ocid` (
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
  UNIQUE KEY `cell_lte_ocid_cellid_unique` (`radio`,`mcc`,`mnc`,`lac`,`cid`),
  KEY `cell_lte_ocid_latlon_idx` (`lat`,`lon`),
  KEY `cell_lte_ocid_region_idx` (`region`),
  KEY `cell_lte_ocid_modified_idx` (`modified`),
  KEY `cell_lte_ocid_created_idx` (`created`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8
'''
    op.execute(sa.text(stmt))

    log.info('Recreate cell_wcdma_ocid table.')
    stmt = '''\
CREATE TABLE `cell_wcdma_ocid` (
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
  UNIQUE KEY `cell_wcdma_ocid_cellid_unique` (`radio`,`mcc`,`mnc`,`lac`,`cid`),
  KEY `cell_wcdma_ocid_latlon_idx` (`lat`,`lon`),
  KEY `cell_wcdma_ocid_modified_idx` (`modified`),
  KEY `cell_wcdma_ocid_region_idx` (`region`),
  KEY `cell_wcdma_ocid_created_idx` (`created`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8
'''
    op.execute(sa.text(stmt))
