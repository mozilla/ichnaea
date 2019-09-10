"""Add fallback schema

Revision ID: 5797389a3842
Revises: 30a4df7eafd5
Create Date: 2017-08-07 15:21:02.987638
"""

import logging

from alembic import op
import sqlalchemy as sa


log = logging.getLogger("alembic.migration")
revision = "5797389a3842"
down_revision = "30a4df7eafd5"


def upgrade():
    log.info("Add fallback_schema column to api_key table.")
    stmt = """\
ALTER TABLE api_key
ADD COLUMN `fallback_schema` varchar(64) DEFAULT NULL AFTER `fallback_name`
"""
    op.execute(sa.text(stmt))


def downgrade():
    log.info("Drop fallback_schema column from api_key table.")
    stmt = """\
ALTER TABLE api_key
DROP COLUMN `fallback_schema`
"""
    op.execute(sa.text(stmt))
