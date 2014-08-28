import boto
import csv
import gzip
import os
import shutil
import tempfile
import time
from contextlib import contextmanager
from datetime import datetime, timedelta
from pytz import UTC
from sqlalchemy.sql import select, and_

from ichnaea.async.task import DatabaseTask
from ichnaea.models import (
    cell_table,
    ocid_cell_table,
    CELLID_LAC,
    RADIO_TYPE,
    RADIO_TYPE_INVERSE,
    normalized_cell_dict
)
from ichnaea.worker import celery
from ichnaea import util


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
CELL_FIELD_INDICES = dict(
    [(e, i) for (i, e) in enumerate(CELL_FIELDS)]
)

# The list of cell columns, we actually need for the export
CELL_COLUMN_NAMES = [
    'created', 'modified', 'lat', 'lon',
    'radio', 'mcc', 'mnc', 'lac', 'cid', 'psc',
    'range', 'total_measures']

CELL_COLUMN_NAME_INDICES = dict(
    [(e, i) for (i, e) in enumerate(CELL_COLUMN_NAMES)]
)
CELL_COLUMNS = []
for name in CELL_COLUMN_NAMES:
    CELL_COLUMNS.append(getattr(cell_table.c, name))


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


def make_cell_export_dict(row):
    d = dict()
    ix = CELL_COLUMN_NAME_INDICES

    for field in CELL_FIELDS:
        if field in ix:
            d[field] = row[ix[field]]

    # Fix up specific entry formatting
    radio = row[ix['radio']]
    if radio is None:
        radio = -1

    psc = row[ix['psc']]
    if psc is None or psc == -1:
        psc = ''

    d['radio'] = RADIO_TYPE_INVERSE[radio].upper()
    d['created'] = int(time.mktime(row[ix['created']].timetuple()))
    d['updated'] = int(time.mktime(row[ix['modified']].timetuple()))
    d['samples'] = row[ix['total_measures']]
    d['changeable'] = 1
    d['averageSignal'] = ''
    d['psc'] = psc
    return d


def make_cell_import_dict(row):

    def val(key, default):
        if key in row and row[key] != '':
            return row[key]
        else:
            return default

    d = dict()

    d['created'] = datetime.fromtimestamp(
        int(val('created', 0))).replace(tzinfo=UTC)

    d['modified'] = datetime.fromtimestamp(
        int(val('updated', 0))).replace(tzinfo=UTC)

    d['lat'] = float(val('lat', -255))
    d['lon'] = float(val('lon', -255))

    d['radio'] = RADIO_TYPE.get(row['radio'].lower(), -1)

    for k in ['mcc', 'mnc', 'lac', 'cid', 'psc']:
        d[k] = int(val(k, -1))

    d['range'] = int(float(val('range', 0)))

    d['total_measures'] = int(val('samples', -1))
    d['changeable'] = bool(val('changeable', True))
    return normalized_cell_dict(d)


def write_stations_to_csv(sess, table, columns, cond, path, make_dict, fields):
    with GzipFile(path, 'wb') as f:
        w = csv.DictWriter(f, fields, extrasaction='ignore')
        limit = 10000
        offset = 0
        # Write header row
        w.writerow(dict([(field, field) for field in fields]))
        while True:
            q = select(columns=columns).where(cond).limit(
                limit).offset(offset).order_by(table.c.id)
            rows = sess.execute(q).fetchall()
            if rows:
                rows = [make_dict(d) for d in rows]
                w.writerows(rows)
                offset += limit
            else:
                break


def write_stations_to_s3(path, bucketname):
    conn = boto.connect_s3()
    bucket = conn.get_bucket(bucketname)
    k = boto.s3.key.Key(bucket)
    k.key = "export/" + os.path.split(path)[-1]
    k.set_contents_from_filename(path, reduced_redundancy=True)


def export_modified_stations(sess, table, columns, cond,
                             filename, fields, bucket):
    with selfdestruct_tempdir() as d:
        path = os.path.join(d, filename)
        write_stations_to_csv(sess, table, columns, cond,
                              path, make_cell_export_dict, fields)
        write_stations_to_s3(path, bucket)


@celery.task(base=DatabaseTask, bind=True)
def export_modified_cells(self, hourly=True, bucket=None):
    if bucket is None:
        bucket = self.app.s3_settings['assets_bucket']
    now = util.utcnow()

    if hourly:
        end_time = now.replace(minute=0, second=0)
        file_time = end_time
        file_type = 'diff'
        start_time = end_time - timedelta(hours=1)
        cond = and_(cell_table.c.modified >= start_time,
                    cell_table.c.modified < end_time,
                    cell_table.c.cid != CELLID_LAC)
    else:
        file_time = now.replace(hour=0, minute=0, second=0)
        file_type = 'full'
        cond = cell_table.c.cid != CELLID_LAC

    filename = 'MLS-%s-cell-export-' % file_type
    filename = filename + file_time.strftime('%Y-%m-%dT%H0000.csv.gz')
    try:
        with self.db_session() as sess:
            export_modified_stations(sess, cell_table, CELL_COLUMNS, cond,
                                     filename, CELL_FIELDS, bucket)
    except Exception as exc:  # pragma: no cover
        self.heka_client.raven('error')
        raise self.retry(exc=exc)


def import_stations(sess, table, columns,
                    filename, make_dict, fields):

    with GzipFile(filename, 'rb') as f:
        w = csv.DictReader(f, fields)
        batch = 10000
        rows = []
        ins = table.insert(
            on_duplicate=('modified = values(modified), ' +
                          'total_measures = values(total_measures), ' +
                          'lat = values(lat), ' +
                          'lon = values(lon), ' +
                          'psc = values(psc), ' +
                          '`range` = values(`range`)'))
        for row in w:
            d = make_dict(row)
            if d is not None:
                rows.append(d)
            if len(rows) == batch:
                sess.execute(ins, rows)
                rows = []
        if rows:
            sess.execute(ins, rows)


@celery.task(base=DatabaseTask, bind=True)
def import_ocid_cells(self, filename=None, sess=None):
    try:
        with self.db_session() as dbsess:
            if sess is None:
                sess = dbsess
            import_stations(sess, ocid_cell_table, CELL_COLUMNS,
                            filename, make_cell_import_dict,
                            CELL_FIELDS)
    except Exception as exc:  # pragma: no cover
        self.heka_client.raven('error')
        raise self.retry(exc=exc)
