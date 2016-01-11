"""Add allow_locate column.

Revision ID: 9743e7b8a17a
Revises: 5d245a440c6f
Create Date: 2016-01-11 15:19:32.804677
"""

import logging

from alembic import op
import sqlalchemy as sa


log = logging.getLogger('alembic.migration')
revision = '9743e7b8a17a'
down_revision = '5d245a440c6f'


def upgrade():
    log.info('Add allow_locate column to api_key table.')
    op.execute(sa.text(
        'ALTER TABLE api_key '
        'ADD COLUMN `allow_locate` TINYINT(1) AFTER `allow_fallback`'
    ))
    op.execute(sa.text('UPDATE api_key SET allow_locate = 1'))


def downgrade():
    op.execute(sa.text('ALTER TABLE api_key DROP COLUMN `allow_locate`'))
