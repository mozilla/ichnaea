"""Base schema.

Revision ID: 000000000000
Revises: None
Create Date: 2016-04-14 14:08:27.104535
"""

from collections import namedtuple
import logging
import os.path

from alembic import op
import sqlalchemy as sa
from sqlalchemy import text


DBCreds = namedtuple("DBCreds", "user pwd")


log = logging.getLogger("alembic.migration")
revision = "000000000000"
down_revision = None

HERE = os.path.dirname(__file__)
BASE_SQL_PATH = os.path.join(HERE, "base.sql")

with open(BASE_SQL_PATH, "r") as fd:
    BASE_SQL = fd.read().strip()


def upgrade():
    conn = op.get_bind()

    log.info("Create initial base schema")
    op.execute(sa.text(BASE_SQL))
    log.info("Initial schema created.")

    # Setup internal export
    stmt = text("select name from export_config")
    result = conn.execute(stmt).fetchall()
    if not ("internal",) in result:
        stmt = text(
            """\
INSERT INTO export_config (`name`, `batch`, `schema`)
VALUES ('internal', 100, 'internal')
"""
        )
        conn.execute(stmt)


def downgrade():
    log.info("Drop initial schema.")
    lines = BASE_SQL.split("\n")
    tables = set()
    for line in lines:
        if "CREATE TABLE" not in line:
            continue
        name = line.split("`")[1]
        tables.add(name)
    tables = list(tables)
    tables.sort()
    for table in tables:
        stmt = "DROP TABLE `%s`" % table
        op.execute(sa.text(stmt))
    log.info("Initial schema dropped.")
