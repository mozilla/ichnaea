"""added maxreq to apikey

Revision ID: 177fd68744a4
Revises: 10f2bbd0fdaa
Create Date: 2014-06-17 10:42:04.074647

"""

# revision identifiers, used by Alembic.
revision = '177fd68744a4'
down_revision = '10f2bbd0fdaa'

from alembic import op
import sqlalchemy as sa


def upgrade():
    op.add_column('api_key', sa.Column('maxreq', sa.Integer()))


def downgrade():
    op.drop_column('api_key', 'maxreq')
