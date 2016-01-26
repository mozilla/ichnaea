"""add bluetooth region stat

Revision ID: 4b11500c9014
Revises: b247526b9501
Create Date: 2016-01-26 22:49:08.201425
"""

import logging

from alembic import op
import sqlalchemy as sa


log = logging.getLogger('alembic.migration')
revision = '4b11500c9014'
down_revision = 'b247526b9501'


def upgrade():
    log.info('Add blue column to region_stat table.')
    stmt = ('ALTER TABLE region_stat '
            'ADD COLUMN `blue` BIGINT(20) unsigned DEFAULT NULL AFTER `lte`')
    op.execute(sa.text(stmt))


def downgrade():
    log.info('Drop blue column from region_stat table.')
    stmt = ('ALTER TABLE region_stat '
            'DROP COLUMN `blue`')
    op.execute(sa.text(stmt))
