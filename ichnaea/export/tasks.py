from ichnaea.async.task import DatabaseTask
from ichnaea.models import (Cell, CELLID_LAC)
from ichnaea.worker import celery
from ichnaea import util
from datetime import timedelta
import boto
import csv
import gzip
import tempfile
import shutil
from contextlib import contextmanager
import os

CELL_FIELDS = ['lat', 'lon', 'mcc', 'mnc', 'lac', 'cid', 'psc']


@contextmanager
def selfdestruct_tempdir():
    base_path = tempfile.mkdtemp()
    try:
        yield base_path
    finally:
        shutil.rmtree(base_path)


# Python 2.6 Gzipfile doesn't have __exit__
class GzipFile(gzip.GzipFile):
    def __enter__(self):
        if self.fileobj is None:
            raise ValueError("I/O operation on closed GzipFile object")
        return self

    def __exit__(self, *args):
        self.close()


def write_stations_to_csv(path, fieldnames, stations):
    with GzipFile(path, 'wb') as f:
        w = csv.DictWriter(f, fieldnames, extrasaction='ignore')
        for s in stations:
            w.writerow(s.__dict__)


def write_stations_to_s3(path, bucketname):
    conn = boto.connect_s3()
    bucket = conn.get_bucket(bucketname)
    k = boto.s3.key.Key(bucket)
    k.key = os.path.split(path)[-1]
    k.set_acl('public-read')
    k.set_contents_from_filename(path)


def export_modified_stations(stations, filename, bucket):
    with selfdestruct_tempdir() as d:
        path = os.path.join(d, filename)
        write_stations_to_csv(path, CELL_FIELDS, stations)
        write_stations_to_s3(path, bucket)


@celery.task(base=DatabaseTask, bind=True)
def export_modified_cells(self, bucket=None, since=None):
    if bucket is None:
        bucket = self.app.s3_settings['export_bucket'],
    now = util.utcnow()
    if since is None:
        since = now - timedelta(hours=1)
    filename = now.strftime('MLS-cell-export-%Y-%m-%dT%H%M%S.csv.gz')
    try:
        with self.db_session() as session:
            cells = session.query(Cell).filter(
                Cell.modified >= since,
                Cell.cid != CELLID_LAC).all()
            export_modified_stations(cells, filename, bucket)
    except Exception as exc:  # pragma: no cover
        self.heka_client.raven('error')
        raise self.retry(exc=exc)
