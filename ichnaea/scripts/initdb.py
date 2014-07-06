import argparse
import os
import sys

from alembic.config import Config
from alembic import command
from sqlalchemy import text
from sqlalchemy.exc import ProgrammingError

from ichnaea.config import read_config
# make sure content models are imported
from ichnaea.content import models  # NOQA
from ichnaea.db import _Model
from ichnaea.db import Database
from ichnaea.heka_logging import configure_heka


def add_test_api_key(conn):
    stmt = text('select valid_key from api_key')
    result = conn.execute(stmt).fetchall()
    if not ('test', ) in result:
        stmt = text('insert into api_key (valid_key, shortname) '
                    'values ("test", "test")')
        conn.execute(stmt)


def create_schema(engine, alembic_cfg, location_cfg):
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

        add_test_api_key(conn)

        trans.commit()

    # Now stamp the latest alembic version
    if not old_version:
        command.stamp(alembic_cfg, "head")
    command.current(alembic_cfg)


def main(argv, _db_master=None, _heka_client=None):
    parser = argparse.ArgumentParser(
        prog=argv[0], description='Initialize Ichnaea database')

    parser.add_argument('--alembic_ini',
                        help='Path to the alembic migration config.')
    parser.add_argument('--location_ini',
                        help='Path to the ichnaea app config.')
    parser.add_argument('--initdb', action='store_true',
                        help='Initialize database')

    args = parser.parse_args(argv[1:])

    if args.initdb:
        # Either use explicit config file location or fallback
        # on environment variable or finally file in current directory
        if not args.location_ini:
            location_ini = os.environ.get('ICHNAEA_CFG', 'ichnaea.ini')
        else:
            location_ini = args.location_ini
        location_ini = os.path.abspath(location_ini)
        location_cfg = read_config(filename=location_ini)

        # Either use explicit config file location or fallback
        # to a file in the same directory as the ichnaea.ini
        if not args.alembic_ini:
            alembic_ini = os.path.join(
                os.path.dirname(location_ini), 'alembic.ini')
        else:
            alembic_ini = args.alembic_ini
        alembic_ini = os.path.abspath(alembic_ini)
        alembic_cfg = Config(alembic_ini)
        alembic_section = alembic_cfg.get_section('alembic')

        if _db_master is None:
            db_master = Database(alembic_section['sqlalchemy.url'])
        else:
            db_master = _db_master
        configure_heka(location_ini, _heka_client=_heka_client)

        engine = db_master.engine
        create_schema(engine, alembic_cfg, location_cfg)
    else:
        parser.print_help()


def console_entry():  # pragma: no cover
    main(sys.argv)
