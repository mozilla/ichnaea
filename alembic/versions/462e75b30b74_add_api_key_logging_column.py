"""Add api key logging column

Revision ID: 462e75b30b74
Revises: 48f67ea76ef7
Create Date: 2014-11-18 13:05:45.277181

"""

# revision identifiers, used by Alembic.
revision = '462e75b30b74'
down_revision = '48f67ea76ef7'

from alembic import op
import sqlalchemy as sa


def upgrade():
    stmt = "ALTER TABLE api_key ADD COLUMN log tinyint(1) AFTER maxreq"
    op.execute(sa.text(stmt))


def downgrade():
    op.drop_column('api_key', 'log')
