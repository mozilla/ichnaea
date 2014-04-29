"""use api_key table to use 40 character columns

Revision ID: 51ba8090058d
Revises: 2a311d11a90d
Create Date: 2014-04-22 14:23:37.378665

"""

# revision identifiers, used by Alembic.
revision = '51ba8090058d'
down_revision = '2a311d11a90d'

from alembic import op
import sqlalchemy as sa


def upgrade():
    op.alter_column('api_key',
                    'valid_key',
                    type_=sa.String(40),
                    existing_type=sa.String(36))


def downgrade():
    op.alter_column('api_key',
                    'valid_key',
                    type_=sa.String(36),
                    existing_type=sa.String(40))
