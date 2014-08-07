from ichnaea.async.task import DatabaseTask
from ichnaea.models import (Cell, CELLID_LAC, RADIO_TYPE_INVERSE)
from ichnaea.worker import celery
from ichnaea import util
from datetime import timedelta
import time
import boto
import csv
import gzip
import tempfile
import shutil
from contextlib import contextmanager
import os

CELL_FIELDS = ["radio",
               "mcc",
               "mnc",  # mnc/sid
               "lac",  # lac/tac/nid
               "cid",  # cellid/rnc+cid/bid
               "psc",  # psc/pci
               "lon",
               "lat",
               "range",
               "samples",
               "changeable",
               "created",
               "updated",
               "averageSignal"]

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


def make_cell_dict(cell):

    d = dict()
    for field in CELL_FIELDS:
        if field in cell.__dict__:
            d[field] = cell.__dict__[field]

    # Fix up specific entry formatting
    radio = cell.radio
    if radio is None:
        radio = -1

    d['radio'] = RADIO_TYPE_INVERSE[radio].upper()
    d['created'] = int(time.mktime(cell.created.timetuple()))
    d['updated'] = int(time.mktime(cell.modified.timetuple()))
    d['samples'] = cell.total_measures
    d['changeable'] = 1
    d['averageSignal'] = ''
    return d


def write_stations_to_csv(path, make_dict, fieldnames, stations):
    with GzipFile(path, 'wb') as f:
        w = csv.DictWriter(f, fieldnames, extrasaction='ignore')
        for s in stations:
            w.writerow(make_dict(s))


def write_stations_to_s3(path, now, bucketname):
    conn = boto.connect_s3()
    bucket = conn.get_bucket(bucketname)
    k = boto.s3.key.Key(bucket)
    k.key = now.strftime("export/%Y/%m/") + os.path.split(path)[-1]
    k.set_contents_from_filename(path)
    k.set_acl('public-read')


def export_modified_stations(stations, now, filename, bucket):
    with selfdestruct_tempdir() as d:
        path = os.path.join(d, filename)
        write_stations_to_csv(path, make_cell_dict, CELL_FIELDS, stations)
        write_stations_to_s3(path, now, bucket)


@celery.task(base=DatabaseTask, bind=True)
def export_modified_cells(self, bucket=None, since=None):
    if bucket is None:
        bucket = self.app.s3_settings['assets_bucket']
    now = util.utcnow()
    if since is None:
        since = now - timedelta(hours=1)
    filename = now.strftime('MLS-cell-export-%Y-%m-%dT%H%M%S.csv.gz')
    try:
        with self.db_session() as session:
            cells = session.query(Cell).filter(
                Cell.modified >= since,
                Cell.cid != CELLID_LAC).all()
            export_modified_stations(cells, now, filename, bucket)
    except Exception as exc:  # pragma: no cover
        self.heka_client.raven('error')
        raise self.retry(exc=exc)
