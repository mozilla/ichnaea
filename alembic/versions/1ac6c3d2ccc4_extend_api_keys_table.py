"""Extend API keys table

Revision ID: 1ac6c3d2ccc4
Revises: 23a8a4ccc96f
Create Date: 2014-07-06 14:30:02.672998

"""

# revision identifiers, used by Alembic.
revision = '1ac6c3d2ccc4'
down_revision = '23a8a4ccc96f'

from alembic import op
import sqlalchemy as sa


def upgrade():
    op.add_column('api_key', sa.Column('shortname', sa.String(40)))
    op.add_column('api_key', sa.Column('email', sa.String(255)))
    op.add_column('api_key', sa.Column('description', sa.String(255)))


def downgrade():
    op.drop_column('api_key', 'description')
    op.drop_column('api_key', 'email')
    op.drop_column('api_key', 'shortname')
