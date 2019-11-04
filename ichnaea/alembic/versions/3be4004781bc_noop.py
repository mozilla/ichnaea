"""No-op migration for testing deploys

Revision ID: 3be4004781bc
Revises: a0ee5e10f44b
Create Date: 2019-11-04 18:56:29.459718
"""

import logging


log = logging.getLogger("alembic.migration")
revision = "3be4004781bc"
down_revision = "a0ee5e10f44b"


def upgrade():
    pass


def downgrade():
    pass
