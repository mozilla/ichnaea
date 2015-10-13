"""Change cell_area primary key.


Revision ID: 238aca86fe8d
Revises: 3fd11bfaca02
Create Date: 2015-10-13 15:57:45.873136
"""

import logging

from alembic import op
import sqlalchemy as sa


log = logging.getLogger('alembic.migration')
revision = '238aca86fe8d'
down_revision = '3fd11bfaca02'


def upgrade():
    log.info('Altering cell_area table.')
    stmt = '''\
ALTER TABLE cell_area
CHANGE COLUMN `avg_cell_radius` `avg_cell_radius` int(10) unsigned,
ADD COLUMN `region` varchar(2) AFTER `radius`,
DROP PRIMARY KEY,
ADD PRIMARY KEY(`areaid`),
DROP KEY `cell_area_areaid_unique`,
ADD UNIQUE KEY `cell_area_areaid_unique` (`radio`, `mcc`, `mnc`, `lac`),
ADD INDEX `cell_area_region_radio_idx` (`region`, `radio`),
ADD INDEX `cell_area_created_idx` (`created`),
ADD INDEX `cell_area_modified_idx` (`modified`),
ADD INDEX `cell_area_latlon_idx` (`lat`, `lon`)
'''
    op.execute(sa.text(stmt))


def downgrade():
    log.info('Altering cell_area table.')
    stmt = '''\
ALTER TABLE cell_area
CHANGE COLUMN `avg_cell_radius` `avg_cell_radius` int(11),
DROP COLUMN `region`,
DROP PRIMARY KEY,
ADD PRIMARY KEY(`radio`, `mcc`, `mnc`, `lac`),
DROP KEY `cell_area_areaid_unique`,
ADD UNIQUE KEY `cell_area_areaid_unique` (`areaid`),
DROP INDEX `cell_area_region_radio_idx`,
DROP INDEX `cell_area_created_idx`,
DROP INDEX `cell_area_modified_idx`,
DROP INDEX `cell_area_latlon_idx`
'''
    op.execute(sa.text(stmt))
