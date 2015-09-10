import argparse
import os
import os.path
import sys

from ichnaea.cache import (
    configure_redis,
    redis_pipeline,
)
from ichnaea.config import read_config
from ichnaea.data import ocid
from ichnaea.data.tasks import update_area
from ichnaea.db import (
    configure_db,
    db_worker_session,
)
from ichnaea.log import configure_logging


def load_file(db, redis_client, filename):  # pragma: no cover
    with redis_pipeline(redis_client) as pipe:
        with db_worker_session(db) as session:
            ocid.ImportLocal(
                None, session, pipe,
                update_area_task=update_area)(filename=filename)


def main(argv, _db_rw=None, _redis_client=None):  # pragma: no cover
    parser = argparse.ArgumentParser(
        prog=argv[0], description='Load/import cell data.')
    parser.add_argument('--filename',
                        help='Path to the gzipped csv file.')

    args = parser.parse_args(argv[1:])
    if not args.filename:
        parser.print_help()
        sys.exit(1)

    filename = os.path.abspath(args.filename)
    if not os.path.isfile(filename):
        print('File not found.')
        sys.exit(1)

    configure_logging()
    app_config = read_config()
    db = configure_db(app_config.get('database', 'rw_url'), _db=_db_rw)
    redis_client = configure_redis(
        app_config.get('cache', 'cache_url'), _client=_redis_client)

    load_file(db, redis_client, filename)


def console_entry():  # pragma: no cover
    main(sys.argv)
