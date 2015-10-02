"""add new cell ocid tables

Revision ID: 339d19da63ee
Revises: 26c4b3a7bc51
Create Date: 2015-10-02 13:27:46.984823
"""

import logging

from alembic import op
import sqlalchemy as sa


log = logging.getLogger('alembic.migration')
revision = '339d19da63ee'
down_revision = '26c4b3a7bc51'


def upgrade():
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
`country` varchar(2) DEFAULT NULL,
`avg_cell_radius` int(10) unsigned DEFAULT NULL,
`num_cells` int(10) unsigned DEFAULT NULL,
PRIMARY KEY (`areaid`),
UNIQUE KEY `cell_area_ocid_areaid_unique` (`radio`,`mcc`,`mnc`,`lac`),
KEY `cell_area_ocid_country_radio_idx` (`country`,`radio`),
KEY `cell_area_ocid_created_idx` (`created`),
KEY `cell_area_ocid_modified_idx` (`modified`),
KEY `cell_area_ocid_latlon_idx` (`lat`,`lon`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8
'''
    log.info('Add cell_area_ocid table.')
    op.execute(sa.text(stmt))

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
`cellid` binary(11) NOT NULL,
`radio` tinyint(4) NOT NULL,
`mcc` smallint(6) NOT NULL,
`mnc` smallint(6) NOT NULL,
`lac` smallint(5) unsigned NOT NULL,
`cid` int(10) unsigned NOT NULL,
`psc` smallint(6) DEFAULT NULL,
`radius` int(10) unsigned DEFAULT NULL,
`country` varchar(2) DEFAULT NULL,
`samples` int(10) unsigned DEFAULT NULL,
`source` tinyint(4) DEFAULT NULL,
`block_first` date DEFAULT NULL,
`block_last` date DEFAULT NULL,
`block_count` tinyint(3) unsigned DEFAULT NULL,
PRIMARY KEY (`cellid`),
UNIQUE KEY `cell_ocid_cellid_unique` (`radio`,`mcc`,`mnc`,`lac`,`cid`),
KEY `cell_ocid_country_radio_idx` (`country`,`radio`),
KEY `cell_ocid_created_idx` (`created`),
KEY `cell_ocid_modified_idx` (`modified`),
KEY `cell_ocid_latlon_idx` (`lat`,`lon`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8
'''
    log.info('Add cell_ocid table.')
    op.execute(sa.text(stmt))


def downgrade():
    log.info('Drop cell_area_ocid table')
    op.drop_table('cell_area_ocid')
    log.info('Drop cell_ocid table')
    op.drop_table('cell_ocid')
