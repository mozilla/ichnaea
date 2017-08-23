"""Remove allow_transfer column

Revision ID: a0ee5e10f44b
Revises: 138cb0d71dfb
Create Date: 2017-08-23 12:58:30.440328
"""

import logging

from alembic import op
import sqlalchemy as sa


log = logging.getLogger('alembic.migration')
revision = 'a0ee5e10f44b'
down_revision = '138cb0d71dfb'


def upgrade():
    log.info('Remove allow_transfer column from api_key table.')
    op.execute(sa.text('ALTER TABLE api_key DROP COLUMN `allow_transfer`'))


def downgrade():
    log.info('Add allow_transfer column to api_key table.')
    op.execute(sa.text(
        'ALTER TABLE api_key '
        'ADD COLUMN `allow_transfer` TINYINT(1) AFTER `allow_locate`'
    ))
    op.execute(sa.text(
        'UPDATE api_key SET allow_transfer = 0'
    ))
