"""add station modified times

Revision ID: 4508f02e6cd7
Revises: 2f26a4df27af
Create Date: 2014-08-05 11:30:35.100320

"""

# revision identifiers, used by Alembic.
revision = '4508f02e6cd7'
down_revision = '2f26a4df27af'

from alembic import op
import sqlalchemy as sa


def upgrade():
    stmt = "ALTER TABLE %s ADD COLUMN modified DATETIME AFTER created"

    op.execute(sa.text(stmt % "cell"))
    op.execute("UPDATE cell SET modified = NOW() WHERE modified IS NULL")

    op.execute(sa.text(stmt % "wifi"))
    op.execute("UPDATE wifi SET modified = NOW() WHERE modified IS NULL")


def downgrade():
    op.drop_column('cell', 'modified')
    op.drop_column('wifi', 'modified')
