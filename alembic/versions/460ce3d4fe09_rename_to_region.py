"""rename to region

Revision ID: 460ce3d4fe09
Revises: 339d19da63ee
Create Date: 2015-10-06 12:23:33.540611
"""

import logging

from alembic import op
import sqlalchemy as sa


log = logging.getLogger('alembic.migration')
revision = '460ce3d4fe09'
down_revision = '339d19da63ee'


def upgrade():
    stmt = '''\
ALTER TABLE cell_ocid
DROP INDEX cell_ocid_country_radio_idx,
CHANGE COLUMN country region varchar(2),
ADD INDEX cell_ocid_region_radio_idx (`region`, `radio`)
'''
    log.info('Modify cell_ocid table.')
    op.execute(sa.text(stmt))

    stmt = '''\
ALTER TABLE cell_area_ocid
DROP INDEX cell_area_ocid_country_radio_idx,
CHANGE COLUMN country region varchar(2),
ADD INDEX cell_area_ocid_region_radio_idx (`region`, `radio`)
'''
    log.info('Modify cell_area_ocid table.')
    op.execute(sa.text(stmt))

    for i in range(16):
        table = 'wifi_shard_%x' % i
        stmt = '''\
    ALTER TABLE {table}
    DROP INDEX {table}_country_idx,
    CHANGE COLUMN country region varchar(2),
    ADD INDEX {table}_region_idx (`region`)
    '''
        log.info('Modify %s table.', table)
        op.execute(sa.text(stmt.format(table=table)))


def downgrade():
    stmt = '''\
ALTER TABLE cell_ocid
DROP INDEX cell_ocid_region_radio_idx,
CHANGE COLUMN region country varchar(2),
ADD INDEX cell_ocid_country_radio_idx (`country`, `radio`)
'''
    log.info('Modify cell_ocid table.')
    op.execute(sa.text(stmt))

    stmt = '''\
ALTER TABLE cell_area_ocid
DROP INDEX cell_area_ocid_region_radio_idx,
CHANGE COLUMN region country varchar(2),
ADD INDEX cell_area_ocid_country_radio_idx (`country`, `radio`)
'''
    log.info('Modify cell_area_ocid table.')
    op.execute(sa.text(stmt))

    for i in range(16):
        table = 'wifi_shard_%x' % i
        stmt = '''\
    ALTER TABLE {table}
    DROP INDEX {table}_region_idx,
    CHANGE COLUMN region country varchar(2),
    ADD INDEX {table}_country_idx (`country`)
    '''
        log.info('Modify %s table.', table)
        op.execute(sa.text(stmt.format(table=table)))
