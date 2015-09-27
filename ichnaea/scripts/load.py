import argparse
import os
import os.path
import sys

from ichnaea.async.app import celery_app
from ichnaea.async.config import configure_data
from ichnaea.cache import (
    configure_redis,
    redis_pipeline,
)
from ichnaea.config import read_config
from ichnaea.data import ocid
from ichnaea.db import (
    configure_db,
    db_worker_session,
)
from ichnaea.log import configure_logging


class FakeTask(object):

    def __init__(self, app):  # pragma: no cover
        self.app = app


def load_file(db, redis_client, datatype, filename):  # pragma: no cover
    celery_app.data_queues = configure_data(redis_client)
    task = FakeTask(celery_app)
    with redis_pipeline(redis_client) as pipe:
        with db_worker_session(db) as session:
            ocid.ImportLocal(
                task, session, pipe, cell_type=datatype)(filename=filename)


def main(argv, _db_rw=None, _redis_client=None):  # pragma: no cover
    parser = argparse.ArgumentParser(
        prog=argv[0], description='Load/import cell data.')
    parser.add_argument('--datatype', default='ocid',
                        help='Type of the data file, e.g. ocid')
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

    datatype = args.datatype
    if datatype not in ('cell', 'ocid'):
        print('Unknown data type.')
        sys.exit(1)

    configure_logging()
    app_config = read_config()
    db = configure_db(app_config.get('database', 'rw_url'), _db=_db_rw)
    redis_client = configure_redis(
        app_config.get('cache', 'cache_url'), _client=_redis_client)

    load_file(db, redis_client, datatype, filename)


def console_entry():  # pragma: no cover
    main(sys.argv)
