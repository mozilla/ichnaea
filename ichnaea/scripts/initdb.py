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


def main(argv, _db_master=None, _heka_client=None):
    parser = argparse.ArgumentParser(
        prog=argv[0], description='Initialize Ichnaea database')

    parser.add_argument('--initdb', action='store_true',
                        help='Initialize database')

    args = parser.parse_args(argv[1:])

    if args.initdb:
        conf = read_config()
        db_master = Database(conf.get('ichnaea', 'db_master'))
        configure_heka(conf.filename, _heka_client=_heka_client)

        old_version = False
        engine = db_master.engine
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
            trans.commit()

        # Now stamp the latest alembic version
        ini = os.environ.get('ICHNAEA_CFG', 'ichnaea.ini')
        alembic_ini = os.path.join(os.path.split(ini)[0], 'alembic.ini')
        alembic_cfg = Config(alembic_ini)
        if not old_version:
            command.stamp(alembic_cfg, "head")
        command.current(alembic_cfg)
    else:
        parser.print_help()


def console_entry():  # pragma: no cover
    main(sys.argv)
