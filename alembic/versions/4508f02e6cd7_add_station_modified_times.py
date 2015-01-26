"""add station modified times

Revision ID: 4508f02e6cd7
Revises: None
Create Date: 2014-08-05 11:30:35.100320

"""

# revision identifiers, used by Alembic.
revision = '4508f02e6cd7'
down_revision = None

from alembic import op
import sqlalchemy as sa


def upgrade():
    add_stmt = "ALTER TABLE %s ADD COLUMN modified DATETIME AFTER created"
    update_stmt = "UPDATE %s SET modified = NOW() WHERE modified IS NULL"

    op.execute(sa.text(add_stmt % "cell"))
    op.execute(sa.text(update_stmt % "cell"))

    op.execute(sa.text(add_stmt % "wifi"))
    op.execute(sa.text(update_stmt % "wifi"))


def downgrade():
    op.drop_column('cell', 'modified')
    op.drop_column('wifi', 'modified')
