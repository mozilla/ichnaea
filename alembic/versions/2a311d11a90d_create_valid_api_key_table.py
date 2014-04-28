"""create valid api key table

Revision ID: 2a311d11a90d
Revises: None
Create Date: 2014-04-22 13:50:03.556305

"""

# revision identifiers, used by Alembic.
revision = '2a311d11a90d'
down_revision = None

from alembic import op
import sqlalchemy as sa


def upgrade():
    op.create_table('api_key',
                    sa.Column('valid_key', sa.String(36), primary_key=True),
                    mysql_engine='InnoDB',
                    mysql_charset='utf8',
                    )


def downgrade():
    op.drop_table('api_key')
