"""Add datamap modified index

Revision ID: d2d9ecb12edc
Revises: cad2875fd8cb
Create Date: 2017-02-28 12:30:04.804598
"""

import logging

from alembic import op
import sqlalchemy as sa


log = logging.getLogger('alembic.migration')
revision = 'd2d9ecb12edc'
down_revision = 'cad2875fd8cb'


def upgrade():
    stmt_add_index = '''\
ALTER TABLE datamap_{id}
ADD INDEX `datamap_{id}_modified_idx` (`modified`)
'''
    for shard_id in ('ne', 'se', 'sw', 'nw'):
        op.execute(sa.text(stmt_add_index.format(id=shard_id)))


def downgrade():
    stmt_drop_index = '''\
ALTER TABLE datamap_{id}
DROP KEY `datamap_{id}_modified_idx`
'''
    for shard_id in ('ne', 'se', 'sw', 'nw'):
        op.execute(sa.text(stmt_drop_index.format(id=shard_id)))
