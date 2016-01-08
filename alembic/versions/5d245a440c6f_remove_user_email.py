"""Remove user emails.

Revision ID: 5d245a440c6f
Revises: d350610e27e
Create Date: 2016-01-08 15:07:29.137763
"""

import logging

from alembic import op
import sqlalchemy as sa


log = logging.getLogger('alembic.migration')
revision = '5d245a440c6f'
down_revision = 'd350610e27e'


def upgrade():
    log.info('Nullify email column in user table.')
    stmt = 'UPDATE user SET `email` = NULL'
    op.execute(sa.text(stmt))


def downgrade():
    pass
