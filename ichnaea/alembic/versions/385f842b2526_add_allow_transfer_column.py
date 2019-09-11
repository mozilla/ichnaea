"""Add allow_transfer column to api_key table.

Revision ID: 385f842b2526
Revises: 1bdf1028a085
Create Date: 2016-07-06 07:41:50.004775
"""

import logging

from alembic import op
import sqlalchemy as sa


log = logging.getLogger("alembic.migration")
revision = "385f842b2526"
down_revision = "1bdf1028a085"


def upgrade():
    log.info("Add allow_transfer column to api_key table.")
    op.execute(
        sa.text(
            "ALTER TABLE api_key "
            "ADD COLUMN `allow_transfer` TINYINT(1) AFTER `allow_locate`"
        )
    )
    op.execute(sa.text("UPDATE api_key SET allow_transfer = 0"))


def downgrade():
    op.execute(sa.text("ALTER TABLE api_key DROP COLUMN `allow_transfer`"))
