"""remove api_key extra fields

Revision ID: c1efc747c9
Revises: 4f12bf0c0828
Create Date: 2015-08-18 22:35:49.220968
"""

import logging

from alembic import op
import sqlalchemy as sa


log = logging.getLogger('alembic.migration')
revision = 'c1efc747c9'
down_revision = '4f12bf0c0828'


def upgrade():
    stmt = "ALTER TABLE api_key DROP COLUMN `email`, DROP COLUMN `description`"
    op.execute(sa.text(stmt))


def downgrade():
    pass
