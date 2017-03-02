"""
Initialize Ichnaea database schema and users for the first time.

Script is installed as `location_initdb`.
"""

import argparse
from collections import namedtuple
import sys

from alembic import command
from sqlalchemy import text
from sqlalchemy.exc import ProgrammingError

from ichnaea.config import (
    ALEMBIC_CFG,
    DB_RO_URI,
    DB_RW_URI,
)
from ichnaea.db import configure_db
from ichnaea.log import configure_raven

# make sure all models are imported
from ichnaea.models import _Model

DBCreds = namedtuple('DBCreds', 'user pwd')


def _db_creds(connection):
    # for example 'mysql+pymysql://user:pwd@localhost/location'
    result = connection.split('@')[0].split('//')[-1].split(':')
    return DBCreds(*result)


def add_api_key(conn):  # pragma: no cover
    stmt = text('select valid_key from api_key')
    result = conn.execute(stmt).fetchall()
    if not ('test', ) in result:
        stmt = text('INSERT INTO api_key (valid_key, allow_locate) '
                    'VALUES ("test", 1)')
        conn.execute(stmt)


def add_export_config(conn):  # pragma: no cover
    stmt = text('select name from export_config')
    result = conn.execute(stmt).fetchall()
    if not ('internal', ) in result:
        stmt = text('''\
INSERT INTO export_config (`name`, `batch`, `schema`, `skip_keys`)
VALUES ("internal", 100, "internal", "test")
''')
        conn.execute(stmt)


def add_users(conn):  # pragma: no cover
    # We don't take into account hostname or database restrictions
    # the users / grants, but use global privileges.
    creds = {}
    creds['rw'] = _db_creds(DB_RW_URI)
    creds['ro'] = _db_creds(DB_RO_URI)

    stmt = text('SELECT user FROM mysql.user')
    result = conn.execute(stmt)
    userids = set([r[0] for r in result.fetchall()])

    create_stmt = text('CREATE USER :user IDENTIFIED BY :pwd')
    grant_stmt = text('GRANT delete, insert, select, update ON *.* TO :user')
    for cred in creds.values():
        if cred.user not in userids:
            conn.execute(create_stmt.bindparams(user=cred.user, pwd=cred.pwd))
            conn.execute(grant_stmt.bindparams(user=cred.user))


def create_schema(engine):  # pragma: no cover
    old_version = False
    with engine.connect() as conn:
        trans = conn.begin()
        stmt = text('select version_num from alembic_version')
        try:
            result = conn.execute(stmt).fetchall()
            if len(result):
                old_version = True
        except ProgrammingError:
            pass

        if not old_version:
            _Model.metadata.create_all(engine)

        add_api_key(conn)
        add_export_config(conn)
        add_users(conn)

        trans.commit()

    # Now stamp the latest alembic version
    if not old_version:
        command.stamp(ALEMBIC_CFG, 'head')
    command.current(ALEMBIC_CFG)


def main(argv, _db=None, _raven_client=None):  # pragma: no cover
    parser = argparse.ArgumentParser(
        prog=argv[0], description='Initialize Ichnaea database.')

    parser.add_argument('--initdb', action='store_true',
                        help='Initialize database.')

    args = parser.parse_args(argv[1:])
    if args.initdb:
        configure_raven(transport='sync', _client=_raven_client)
        db = configure_db('ddl', _db=_db)
        create_schema(db.engine)
    else:
        parser.print_help()


def console_entry():  # pragma: no cover
    main(sys.argv)
