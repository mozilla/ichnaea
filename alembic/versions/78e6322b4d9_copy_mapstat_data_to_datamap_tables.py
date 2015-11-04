"""copy mapstat data to datamap tables

Revision ID: 78e6322b4d9
Revises: 4e8635b0f4cf
Create Date: 2015-11-04 12:26:13.692906
"""

import logging

from alembic import op
import sqlalchemy as sa


log = logging.getLogger('alembic.migration')
revision = '78e6322b4d9'
down_revision = '4e8635b0f4cf'


def upgrade():
    stmt1 = '''\
ALTER TABLE datamap_{id} DROP KEY `datamap_{id}_created_idx`
'''

    stmt2 = '''\
INSERT INTO datamap_{id}
(grid, created, modified) (
SELECT
UNHEX(CONCAT(LPAD(HEX(`lat` + 90000), 8, 0), LPAD(HEX(`lon` + 180000), 8, 0))),
`time`, `time`
FROM mapstat WHERE
lat {lat_crit} AND lon {lon_crit}
)
'''

    stmt3 = '''\
ALTER TABLE datamap_{id} ADD INDEX `datamap_{id}_created_idx` (`created`)
'''

    stmt4 = 'OPTIMIZE TABLE datamap_{id}'

    shards = [
        ('ne', '>= 36000', '>= 5000'),
        ('nw', '>= 36000', '< 5000'),
        ('se', '< 36000', '>= 5000'),
        ('sw', '< 36000', '< 5000'),
    ]
    for shard_id, lat_crit, lon_crit in shards:
        log.info('Drop datamap_%s created index.' % shard_id)
        op.execute(sa.text(stmt1.format(id=shard_id)))

        log.info('Fill datamap_%s table.' % shard_id)
        op.execute(sa.text(stmt2.format(
            id=shard_id, lat_crit=lat_crit, lon_crit=lon_crit)))

        log.info('Add datamap_%s created index.' % shard_id)
        op.execute(sa.text(stmt3.format(id=shard_id)))

        log.info('Optimize datamap_%s table.' % shard_id)
        op.execute(sa.text(stmt4.format(id=shard_id)))


def downgrade():
    pass
