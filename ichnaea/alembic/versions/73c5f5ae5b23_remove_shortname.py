"""Remove api key shortname column.

Revision ID: 73c5f5ae5b23
Revises: d2d9ecb12edc
Create Date: 2017-07-06 13:22:30.157361
"""

import logging

from alembic import op
import sqlalchemy as sa


log = logging.getLogger("alembic.migration")
revision = "73c5f5ae5b23"
down_revision = "d2d9ecb12edc"


def upgrade():
    log.info("Drop shortname column from api_key table.")
    op.execute(sa.text("ALTER TABLE api_key " "DROP COLUMN `shortname`"))


def downgrade():
    log.info("Add shortname column to api_key table.")
    op.execute(
        sa.text(
            "ALTER TABLE api_key "
            "ADD COLUMN `shortname` VARCHAR(40) DEFAULT NULL "
            "AFTER `allow_transfer`"
        )
    )
