"""Add cell modified index

Revision ID: 5214b5cfc5d2
Revises: 4c89b299ffb0
Create Date: 2014-11-03 09:10:18.189127

"""

# revision identifiers, used by Alembic.
revision = '5214b5cfc5d2'
down_revision = '4c89b299ffb0'

from alembic import op
import sqlalchemy as sa


def upgrade():
    stmt = "CREATE INDEX cell_modified_idx ON cell (modified)"
    op.execute(sa.text(stmt))


def downgrade():
    stmt = "DROP INDEX cell_modified_idx ON cell"
    op.execute(sa.text(stmt))
