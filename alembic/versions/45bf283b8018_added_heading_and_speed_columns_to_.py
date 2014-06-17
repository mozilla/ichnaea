"""added heading and speed columns to CellMeasure and WifiMeasure records

Revision ID: 45bf283b8018
Revises: 4323e1f1a0b8
Create Date: 2014-05-30 13:16:26.655710

"""

# revision identifiers, used by Alembic.
revision = '45bf283b8018'
down_revision = '4323e1f1a0b8'

from alembic import op
import sqlalchemy as sa


def upgrade():
    op.add_column('wifi_measure',
                  sa.Column('heading', sa.Float()))
    op.add_column('cell_measure',
                  sa.Column('heading', sa.Float()))

    op.add_column('wifi_measure',
                  sa.Column('speed', sa.Float()))
    op.add_column('cell_measure',
                  sa.Column('speed', sa.Float()))


def downgrade():
    op.drop_column('cell_measure', 'heading')
    op.drop_column('cell_measure', 'speed')
    op.drop_column('wifi_measure', 'heading')
    op.drop_column('wifi_measure', 'speed')
