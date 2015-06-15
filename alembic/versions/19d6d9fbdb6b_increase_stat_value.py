"""increase stat value

Revision ID: 19d6d9fbdb6b
Revises: 38fde2949750
Create Date: 2015-06-15 11:41:06.090423
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '19d6d9fbdb6b'
down_revision = '38fde2949750'


def upgrade():
    stmt = ("ALTER TABLE stat "
            "CHANGE COLUMN `value` `value` bigint(20) unsigned")
    op.execute(sa.text(stmt))


def downgrade():
    pass
