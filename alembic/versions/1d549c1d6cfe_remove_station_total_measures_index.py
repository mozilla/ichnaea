"""remove station total measures index

Revision ID: 1d549c1d6cfe
Revises: 230bbf3fe044
Create Date: 2015-02-28 22:48:34.752635

"""

# revision identifiers, used by Alembic.
revision = '1d549c1d6cfe'
down_revision = '230bbf3fe044'

from alembic import op
import sqlalchemy as sa


def upgrade():
    stmt = 'DROP INDEX cell_total_measures_idx ON cell'
    op.execute(sa.text(stmt))

    stmt = 'DROP INDEX wifi_total_measures_idx ON wifi'
    op.execute(sa.text(stmt))


def downgrade():
    stmt = 'CREATE INDEX cell_total_measures_idx ON cell (total_measures)'
    op.execute(sa.text(stmt))

    stmt = 'CREATE INDEX wifi_total_measures_idx ON wifi (total_measures)'
    op.execute(sa.text(stmt))
