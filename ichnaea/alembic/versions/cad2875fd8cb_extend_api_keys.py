"""Extend api keys with sample_store columns.

Revision ID: cad2875fd8cb
Revises: 385f842b2526
Create Date: 2017-02-22 11:52:47.837989
"""

import logging

from alembic import op
import sqlalchemy as sa


log = logging.getLogger("alembic.migration")
revision = "cad2875fd8cb"
down_revision = "385f842b2526"


def upgrade():
    log.info("Add store_sample_* columns to api_key table.")
    op.execute(
        sa.text(
            "ALTER TABLE api_key "
            "ADD COLUMN `store_sample_locate` TINYINT(4) "
            "AFTER `fallback_cache_expire`, "
            "ADD COLUMN `store_sample_submit` TINYINT(4) "
            "AFTER `store_sample_locate`"
        )
    )
    op.execute(sa.text("UPDATE api_key SET store_sample_locate = 100"))
    op.execute(sa.text("UPDATE api_key SET store_sample_submit = 100"))


def downgrade():
    log.info("Drop store_sample_* columns from api_key table.")
    op.execute(
        sa.text(
            "ALTER TABLE api_key "
            "DROP COLUMN `store_sample_locate`, "
            "DROP COLUMN `store_sample_submit`"
        )
    )
