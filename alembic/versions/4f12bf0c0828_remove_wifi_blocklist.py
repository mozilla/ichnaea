"""remove wifi blocklist

Revision ID: 4f12bf0c0828
Revises: 2127f9dd0ed7
Create Date: 2015-08-18 22:23:14.200544
"""

import logging

from alembic import op


log = logging.getLogger('alembic.migration')
revision = '4f12bf0c0828'
down_revision = '2127f9dd0ed7'


def upgrade():
    log.info('Drop wifi_blacklist table')
    op.drop_table('wifi_blacklist')


def downgrade():
    pass
