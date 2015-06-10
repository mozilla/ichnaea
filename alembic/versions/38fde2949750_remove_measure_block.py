"""remove measure_block

Revision ID: 38fde2949750
Revises: e9c1224f6bb
Create Date: 2015-06-08 14:53:53.467312

"""

from alembic import op

# revision identifiers, used by Alembic.
revision = '38fde2949750'
down_revision = 'e9c1224f6bb'


def upgrade():
    op.drop_table('measure_block')


def downgrade():
    pass
