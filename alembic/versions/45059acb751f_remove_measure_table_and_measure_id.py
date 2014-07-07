"""Remove measure table and measure_id columns

Revision ID: 45059acb751f
Revises: 5357bcae9bfe
Create Date: 2014-07-03 16:26:37.089825

"""

# revision identifiers, used by Alembic.
revision = '45059acb751f'
down_revision = '5357bcae9bfe'

from alembic import op
import sqlalchemy as sa


def upgrade():
    op.drop_column('cell_measure', 'measure_id')
    op.drop_column('wifi_measure', 'measure_id')
    op.drop_table('measure')


def downgrade():
    stmt = ("ALTER TABLE %s ADD COLUMN measure_id bigint(20) "
            "unsigned NOT NULL AFTER report_id")
    op.execute(sa.text(stmt % "cell_measure"))
    op.execute(sa.text(stmt % "wifi_measure"))
    stmt = ("CREATE TABLE `measure` ("
            "`id` bigint(20) unsigned NOT NULL AUTO_INCREMENT, "
            "PRIMARY KEY (`id`)"
            ") ENGINE=InnoDB DEFAULT CHARSET=utf8")
    op.execute(sa.text(stmt))
