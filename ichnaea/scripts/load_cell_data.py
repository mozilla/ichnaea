#!/usr/bin/env python
"""
Load data from a downloaded public export (full or differential)

Download from https://location.services.mozilla.com/downloads
"""

import argparse
import logging
import os
import os.path
import sys

from ichnaea.conf import settings
from ichnaea.db import db_worker_session
from ichnaea.log import configure_logging
from ichnaea.data.public import read_stations_from_csv
from ichnaea.taskapp.config import init_worker
from ichnaea.util import gzip_open


LOGGER = logging.getLogger(__name__)


def get_eager_celery_app():
    """Returns an eagerly configured celery app."""
    # We have to import and fix celery settings before importing the celery_app
    # module since that has a side effect of creating the celery app
    from ichnaea.taskapp import settings as celery_settings

    celery_settings.task_always_eager = True
    celery_settings.task_eager_propagates = True

    from ichnaea.taskapp.app import celery_app

    return celery_app


def main(argv, _db=None):
    parser = argparse.ArgumentParser(
        prog=argv[0],
        description=(
            "Import from public cell data into a local dev environment. "
            "See https://location.services.mozilla.com/downloads"
        ),
    )
    parser.add_argument("filename", help="Path to the csv.gz import file.")

    args = parser.parse_args(argv[1:])

    if not settings("local_dev_env"):
        print("This script can only be run in a local dev environment.")
        print("Set LOCAL_DEV_ENV=True in your environment.")
        return 1

    filename = os.path.abspath(os.path.expanduser(args.filename))
    if not os.path.isfile(filename):
        print("File %s not found." % filename)
        return 1

    configure_logging()
    celery_app = get_eager_celery_app()
    init_worker(celery_app)
    cellarea_queue = celery_app.data_queues["update_cellarea"]

    with db_worker_session(celery_app.db, commit=False) as session:
        with gzip_open(filename, "r") as file_handle:
            read_stations_from_csv(
                session, file_handle, celery_app.redis_client, cellarea_queue
            )
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
