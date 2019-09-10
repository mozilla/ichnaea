"""Add allow_region column to api_key table.

Revision ID: 30a4df7eafd5
Revises: 73c5f5ae5b23
Create Date: 2017-07-06 14:27:19.873645
"""

import logging

from alembic import op
import sqlalchemy as sa


log = logging.getLogger("alembic.migration")
revision = "30a4df7eafd5"
down_revision = "73c5f5ae5b23"


def upgrade():
    log.info("Add allow_region column to api_key table.")
    op.execute(
        sa.text(
            "ALTER TABLE api_key "
            "ADD COLUMN `allow_region` TINYINT(1) AFTER `allow_locate`"
        )
    )
    op.execute(sa.text("UPDATE api_key SET allow_region = 1"))


def downgrade():
    op.execute(sa.text("ALTER TABLE api_key DROP COLUMN `allow_region`"))
