"""add maptat time index

Revision ID: 230bbf3fe044
Revises: 6527bee5ac1
Create Date: 2015-02-27 16:44:10.638236

"""

# revision identifiers, used by Alembic.
revision = '230bbf3fe044'
down_revision = '6527bee5ac1'

from alembic import op
import sqlalchemy as sa


def upgrade():
    stmt = 'CREATE INDEX idx_mapstat_time ON mapstat (time)'
    op.execute(sa.text(stmt))
    stmt = ('UPDATE mapstat SET time = "2014-07-01" '
            'WHERE time < "2014-07-01" OR time is NULL')
    op.execute(sa.text(stmt))
    stmt = 'ANALYZE TABLE mapstat'
    op.execute(sa.text(stmt))


def downgrade():
    stmt = 'DROP INDEX idx_mapstat_time ON mapstat'
    op.execute(sa.text(stmt))
