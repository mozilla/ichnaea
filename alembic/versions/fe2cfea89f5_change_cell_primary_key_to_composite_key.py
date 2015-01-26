"""change cell primary key to composite key

Revision ID: fe2cfea89f5
Revises: 188e749e51ec
Create Date: 2015-01-22 21:02:26.187970

"""

# revision identifiers, used by Alembic.
revision = 'fe2cfea89f5'
down_revision = '188e749e51ec'

from alembic import op
import sqlalchemy as sa


def upgrade():
    stmt = ("ALTER TABLE cell "
            "DROP PRIMARY KEY, "
            "CHANGE COLUMN `id` `id` bigint(20) unsigned, "
            "ADD PRIMARY KEY(radio, mcc, mnc, lac, cid), "
            "DROP KEY cell_idx_unique")
    op.execute(sa.text(stmt))


    stmt = ("ALTER TABLE cell_blacklist "
            "DROP PRIMARY KEY, "
            "CHANGE COLUMN `id` `id` bigint(20) unsigned, "
            "ADD PRIMARY KEY(radio, mcc, mnc, lac, cid), "
            "DROP KEY cell_blacklist_idx_unique")
    op.execute(sa.text(stmt))


def downgrade():
    pass
