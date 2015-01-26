"""Remove ocid_cell id column

Revision ID: 4c89b299ffb0
Revises: 294707f1a078
Create Date: 2014-09-08 16:13:47.340762

"""

# revision identifiers, used by Alembic.
revision = '4c89b299ffb0'
down_revision = '294707f1a078'

from alembic import op
import sqlalchemy as sa


def upgrade():
    stmt = "DELETE FROM ocid_cell"
    op.execute(sa.text(stmt))

    stmt = ("ALTER TABLE ocid_cell "
            "DROP PRIMARY KEY, "
            "CHANGE COLUMN `id` `id` bigint(20) unsigned, "
            "ADD PRIMARY KEY(radio, mcc, mnc, lac, cid), "
            "DROP KEY ocid_cell_idx_unique")
    op.execute(sa.text(stmt))

    stmt = ("ALTER TABLE ocid_cell "
            "CHANGE COLUMN lac lac smallint(5) unsigned, "
            "CHANGE COLUMN cid cid int(10) unsigned")
    op.execute(sa.text(stmt))

    # Only execute this once no process with the old model accesses
    # the database anymore.
    stmt = "ALTER TABLE ocid_cell DROP COLUMN `id`"
    op.execute(sa.text(stmt))

def downgrade():
    pass
