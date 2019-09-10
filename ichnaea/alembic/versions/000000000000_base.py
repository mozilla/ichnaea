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

from ichnaea.conf import settings

DBCreds = namedtuple("DBCreds", "user pwd")


log = logging.getLogger("alembic.migration")
revision = "000000000000"
down_revision = None

HERE = os.path.dirname(__file__)
BASE_SQL_PATH = os.path.join(HERE, "base.sql")

with open(BASE_SQL_PATH, "r") as fd:
    BASE_SQL = fd.read().strip()


def _db_creds(conn_uri):
    # for example 'mysql+pymysql://user:pwd@localhost/location'
    result = conn_uri.split("@")[0].split("//")[-1].split(":")
    return DBCreds(*result)


def _add_users(conn):
    # We don't take into account hostname or database restrictions
    # the users / grants, but use global privileges.
    creds = {}
    creds["rw"] = _db_creds(settings("db_readwrite_uri"))
    creds["ro"] = _db_creds(settings("db_readonly_uri"))

    stmt = text("SELECT user FROM mysql.user")
    result = conn.execute(stmt)
    userids = set([r[0] for r in result.fetchall()])

    create_stmt = text("CREATE USER :user IDENTIFIED BY :pwd")
    grant_stmt = text("GRANT delete, insert, select, update ON *.* TO :user")
    added = False
    for cred in creds.values():
        if cred.user not in userids:
            conn.execute(create_stmt.bindparams(user=cred.user, pwd=cred.pwd))
            conn.execute(grant_stmt.bindparams(user=cred.user))
            userids.add(cred.user)
            added = True
    if added:
        conn.execute("FLUSH PRIVILEGES")


def upgrade():
    conn = op.get_bind()

    log.info("Create initial base schema")
    op.execute(sa.text(BASE_SQL))
    log.info("Initial schema created.")

    # Add rw/ro users
    _add_users(conn)

    # Add test API key
    stmt = text("select valid_key from api_key")
    result = conn.execute(stmt).fetchall()
    if not ("test",) in result:
        stmt = text(
            """\
INSERT INTO api_key
(valid_key, allow_fallback, allow_locate)
VALUES
('test', 0, 1)
"""
        )
        conn.execute(stmt)

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
