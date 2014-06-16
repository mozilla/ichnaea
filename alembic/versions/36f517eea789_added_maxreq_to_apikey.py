"""added maxreq to apikey

Revision ID: 36f517eea789
Revises: 4323e1f1a0b8
Create Date: 2014-06-13 18:31:32.263846

"""

# revision identifiers, used by Alembic.
revision = '36f517eea789'
down_revision = '4323e1f1a0b8'

from alembic import op
import sqlalchemy as sa


def upgrade():
    op.add_column('api_key', sa.Column('maxreq', sa.Integer(), default=0))


def downgrade():
    op.drop_column('api_key', 'maxreq')
