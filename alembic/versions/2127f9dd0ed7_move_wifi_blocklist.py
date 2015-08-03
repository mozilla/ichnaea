"""move wifi blocklist

Revision ID: 2127f9dd0ed7
Revises: 4860cb8e54f5
Create Date: 2015-08-03 11:26:07.111800
"""

import logging

from alembic import op
import sqlalchemy as sa


log = logging.getLogger('alembic.migration')
revision = '2127f9dd0ed7'
down_revision = '4860cb8e54f5'


def upgrade():
    log.info('Move wifi blocklist rows to wifi shard tables.')
    ins_stmt = """\
INSERT IGNORE INTO wifi_shard_{id}
    (`mac`, `block_first`, `block_last`, `block_count`)
    (SELECT UNHEX(`key`) as mac,
        DATE(`time`) as block_first,
        DATE(`time`) as block_last,
        `count` as block_count
    FROM wifi_blacklist WHERE SUBSTR(`key`, 5, 1) = "{id}")
"""
    shard_ids = (
        '0', '1', '2', '3', '4', '5', '6', '7',
        '8', '9', 'a', 'b', 'c', 'd', 'e', 'f',
    )
    flush_stmt = 'SAVEPOINT savepoint_{id}'
    for shard_id in shard_ids:
        log.info('Insert rows into wifi_shard_%s' % shard_id)
        op.execute(sa.text(ins_stmt.format(id=shard_id)))
        op.execute(sa.text(flush_stmt.format(id=shard_id)))

    log.info('Delete rows from wifi_blacklist')
    delete_stmt = 'DELETE FROM wifi_blacklist'
    op.execute(sa.text(delete_stmt))


def downgrade():
    pass
