"""add snr to wifimeasure

Revision ID: 10f2bbd0fdaa
Revises: 45bf283b8018
Create Date: 2014-06-11 16:37:51.739252

"""

# revision identifiers, used by Alembic.
revision = '10f2bbd0fdaa'
down_revision = '45bf283b8018'

from alembic import op
import sqlalchemy as sa


def upgrade():
    op.add_column('wifi_measure',
                  sa.Column('snr', sa.SmallInteger()))


def downgrade():
    op.drop_column('wifi_measure', 'snr')
