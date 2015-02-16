"""tinyint enum columns

Revision ID: 3b8d52a9eac4
Revises: 10542c592089
Create Date: 2015-02-16 15:42:55.185999

"""

# revision identifiers, used by Alembic.
revision = '3b8d52a9eac4'
down_revision = '10542c592089'

from alembic import op
import sqlalchemy as sa

CHANGES = [
    ('measure_block', 'measure_type'),
    ('score', 'key'),
    ('stat', 'key'),
]


def upgrade():
    stmt = "ALTER TABLE {table} CHANGE COLUMN `{column}` `{column}` TINYINT"
    for table, column in CHANGES:
        op.execute(sa.text(stmt.format(table=table, column=column)))


def downgrade():
    stmt = "ALTER TABLE {table} CHANGE COLUMN `{column}` `{column}` SMALLINT(6)"
    for table, column in CHANGES:
        op.execute(sa.text(stmt.format(table=table, column=column)))
