"""drop new_measures indices

Revision ID: 14dbafc4fec2
Revises: 19d6d9fbdb6b
Create Date: 2015-06-15 12:11:22.106270
"""

import logging

from alembic import op
import sqlalchemy as sa

log = logging.getLogger('alembic.migration')
revision = '14dbafc4fec2'
down_revision = '19d6d9fbdb6b'


def upgrade():
    log.info('Drop index from cell table')
    stmt = 'DROP INDEX cell_new_measures_idx ON cell'
    op.execute(sa.text(stmt))

    log.info('Drop index from wifi table')
    stmt = 'DROP INDEX wifi_new_measures_idx ON wifi'
    op.execute(sa.text(stmt))


def downgrade():
    pass
