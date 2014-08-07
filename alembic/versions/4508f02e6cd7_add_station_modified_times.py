"""add station modified times

Revision ID: 4508f02e6cd7
Revises: 2f26a4df27af
Create Date: 2014-08-05 11:30:35.100320

"""

# revision identifiers, used by Alembic.
revision = '4508f02e6cd7'
down_revision = '2f26a4df27af'

from alembic import op
from ichnaea.sa_types import TZDateTime as DateTime
from ichnaea import util
from ichnaea.models import encode_datetime
from sqlalchemy import Column


def upgrade():
    now = encode_datetime(util.utcnow())
    op.add_column('cell', Column('modified', DateTime(), server_default=now))
    op.add_column('wifi', Column('modified', DateTime(), server_default=now))


def downgrade():
    op.drop_column('cell', 'modified')
    op.drop_column('wifi', 'modified')
