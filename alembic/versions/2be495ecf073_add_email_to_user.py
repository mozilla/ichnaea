"""Add email column to user model.

Revision ID: 2be495ecf073
Revises: 48f67ea76ef7
Create Date: 2014-11-17 20:33:16.417367

"""

# revision identifiers, used by Alembic.
revision = '2be495ecf073'
down_revision = '48f67ea76ef7'

from alembic import op
import sqlalchemy as sa


def upgrade():
    op.add_column('user', sa.Column('email', sa.Unicode(255)))


def downgrade():
    op.drop_column('user', 'email')
