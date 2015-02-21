"""remove cell id columns

Revision ID: 6527bee5ac1
Revises: 3b8d52a9eac4
Create Date: 2015-02-21 11:41:34.218948

"""

# revision identifiers, used by Alembic.
revision = '6527bee5ac1'
down_revision = '3b8d52a9eac4'

from alembic import op
import sqlalchemy as sa


def upgrade():
    for table in ('cell', 'cell_blacklist'):
        stmt = "ALTER TABLE {table} DROP COLUMN `id`".format(table=table)
        op.execute(sa.text(stmt))


def downgrade():
    pass
