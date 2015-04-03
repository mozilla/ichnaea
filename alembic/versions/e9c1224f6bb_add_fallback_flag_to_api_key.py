"""add fallback flag to api key

Revision ID: e9c1224f6bb
Revises: 1d549c1d6cfe
Create Date: 2015-04-05 21:36:31.999385

"""

# revision identifiers, used by Alembic.
revision = 'e9c1224f6bb'
down_revision = '1d549c1d6cfe'

from alembic import op
import sqlalchemy as sa


def upgrade():
    stmt = "ALTER TABLE api_key ADD COLUMN allow_fallback tinyint(1) AFTER description"
    op.execute(sa.text(stmt))


def downgrade():
    op.drop_column('api_key', 'allow_fallback')
