from contextlib import contextmanager, closing
import csv
from datetime import datetime, timedelta
import gzip
import os
import shutil
import tempfile

import boto
import requests
from pytz import UTC
from sqlalchemy.sql import (
    and_,
    func,
    select,
)

from ichnaea.async.app import celery_app
from ichnaea.async.task import DatabaseTask
from ichnaea.models import (
    Cell,
    CellArea,
    OCIDCell,
    Radio,
    StatCounter,
    StatKey,
)
from ichnaea.data.tasks import update_area
from ichnaea import util


CELL_FIELDS = [
    'radio', 'mcc', 'mnc', 'lac', 'cid', 'psc',
    'lon', 'lat', 'range', 'samples', 'changeable',
    'created', 'updated', 'averageSignal']
CELL_FIELD_INDICES = dict(
    [(e, i) for (i, e) in enumerate(CELL_FIELDS)]
)
# Map our internal names to the public export names
CELL_HEADER_DICT = dict([(field, field) for field in CELL_FIELDS])
CELL_HEADER_DICT['mnc'] = 'net'
CELL_HEADER_DICT['lac'] = 'area'
CELL_HEADER_DICT['cid'] = 'cell'
CELL_HEADER_DICT['psc'] = 'unit'

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
    if name in ('created', 'modified'):
        CELL_COLUMNS.append(
            func.unix_timestamp(getattr(Cell.__table__.c, name)))
    else:
        CELL_COLUMNS.append(getattr(Cell.__table__.c, name))


@contextmanager
def selfdestruct_tempdir():
    base_path = tempfile.mkdtemp()
    try:
        yield base_path
    finally:
        shutil.rmtree(base_path)


# Python 2.6 Gzipfile doesn't have __exit__
class GzipFile(gzip.GzipFile):

    # Add a default value, as this is used in the __repr__ and only
    # set in the __init__ on successfully opening the file. Sentry/raven
    # would bark on this while trying to capture the stack frame locals.
    fileobj = None

    def __enter__(self):
        if self.fileobj is None:  # pragma: no cover
            raise ValueError('I/O operation on closed GzipFile object')
        return self

    def __exit__(self, *args):
        self.close()


def make_cell_export_dict(row):
    d = {
        'changeable': 1,
        'averageSignal': '',
    }
    ix = CELL_COLUMN_NAME_INDICES

    for field in CELL_FIELDS:
        pos = ix.get(field, None)
        if pos is not None:
            d[field] = row[pos]

    # Fix up specific entry formatting
    radio = row[ix['radio']]

    d['radio'] = radio.name.upper()
    d['created'] = row[ix['created']]
    d['updated'] = row[ix['modified']]
    d['samples'] = row[ix['total_measures']]
    return d


def make_ocid_cell_import_dict(row):

    def val(key, default, _type):
        if key in row and row[key] != '' and row[key] is not None:
            return _type(row[key])
        else:
            return default

    d = dict()

    d['created'] = datetime.fromtimestamp(
        val('created', 0, int)).replace(tzinfo=UTC)

    d['modified'] = datetime.fromtimestamp(
        val('updated', 0, int)).replace(tzinfo=UTC)

    d['lat'] = val('lat', None, float)
    d['lon'] = val('lon', None, float)

    try:
        d['radio'] = Radio[row['radio'].lower()]
    except KeyError:  # pragma: no cover
        d['radio'] = None

    for k in ['mcc', 'mnc', 'lac', 'cid', 'psc']:
        d[k] = val(k, None, int)

    d['range'] = int(val('range', 0, float))
    d['total_measures'] = val('samples', 0, int)
    d['changeable'] = val('changeable', True, bool)
    validated = OCIDCell.validate(d)
    if validated is None:
        return None
    for field in ('radio', 'mcc', 'mnc', 'lac', 'cid'):
        if validated[field] is None:
            return None
    return validated


def write_stations_to_csv(session, table, columns,
                          cond, path, make_dict, fields):
    with GzipFile(path, 'wb') as f:
        w = csv.DictWriter(f, fields, extrasaction='ignore')
        limit = 10000
        offset = 0
        # Write header row
        w.writerow(CELL_HEADER_DICT)
        while True:
            query = (select(columns=columns).where(cond)
                                            .limit(limit)
                                            .offset(offset)
                                            .order_by(table.c.created))
            rows = session.execute(query).fetchall()
            if rows:
                w.writerows([make_dict(r) for r in rows])
                offset += limit
            else:
                break


def write_stations_to_s3(path, bucketname):
    conn = boto.connect_s3()
    bucket = conn.get_bucket(bucketname)
    k = boto.s3.key.Key(bucket)
    k.key = 'export/' + os.path.split(path)[-1]
    k.set_contents_from_filename(path, reduced_redundancy=True)


@celery_app.task(base=DatabaseTask, bind=True)
def export_modified_cells(self, hourly=True, bucket=None):
    if bucket is None:  # pragma: no cover
        bucket = self.app.settings['ichnaea']['s3_assets_bucket']
    if not bucket:  # pragma: no cover
        return

    now = util.utcnow()

    if hourly:
        end_time = now.replace(minute=0, second=0)
        file_time = end_time
        file_type = 'diff'
        start_time = end_time - timedelta(hours=1)
        cond = and_(Cell.__table__.c.modified >= start_time,
                    Cell.__table__.c.modified < end_time,
                    Cell.__table__.c.lat.isnot(None))
    else:
        file_time = now.replace(hour=0, minute=0, second=0)
        file_type = 'full'
        cond = Cell.__table__.c.lat.isnot(None)

    filename = 'MLS-%s-cell-export-' % file_type
    filename = filename + file_time.strftime('%Y-%m-%dT%H0000.csv.gz')

    with selfdestruct_tempdir() as d:
        path = os.path.join(d, filename)
        with self.db_session(commit=False) as session:
            write_stations_to_csv(session, Cell.__table__, CELL_COLUMNS, cond,
                                  path, make_cell_export_dict, CELL_FIELDS)
        write_stations_to_s3(path, bucket)


def import_stations(session, pipe, filename, fields):
    today = util.utcnow().date()

    def commit_batch(ins, rows, commit=True):
        result = session.execute(ins, rows)
        count = result.rowcount
        # apply trick to avoid querying for existing rows,
        # MySQL claims 1 row for an inserted row, 2 for an updated row
        inserted_rows = 2 * len(rows) - count
        changed_rows = count - len(rows)
        assert inserted_rows + changed_rows == len(rows)
        StatCounter(StatKey.unique_ocid_cell, today).incr(pipe, inserted_rows)
        if commit:
            session.commit()
        else:  # pragma: no cover
            session.flush()

    with GzipFile(filename, 'rb') as zip_file:
        csv_reader = csv.DictReader(zip_file, fields)
        batch = 10000
        rows = []
        area_keys = set()
        ins = OCIDCell.__table__.insert(
            on_duplicate=((
                'changeable = values(changeable), '
                'modified = values(modified), '
                'total_measures = values(total_measures), '
                'lat = values(lat), '
                'lon = values(lon), '
                'psc = values(psc), '
                '`range` = values(`range`)')))

        for row in csv_reader:
            # skip any header row
            if csv_reader.line_num == 1 and \
               'radio' in row.values():  # pragma: no cover
                continue

            data = make_ocid_cell_import_dict(row)
            if data is not None:
                rows.append(data)
                area_keys.add(CellArea.to_hashkey(data))

            if len(rows) == batch:  # pragma: no cover
                commit_batch(ins, rows, commit=False)
                rows = []

        if rows:
            commit_batch(ins, rows)

        for area_key in area_keys:
            update_area.delay(area_key, cell_type='ocid')


@celery_app.task(base=DatabaseTask, bind=True)
def import_ocid_cells(self, filename=None, session=None):
    with self.redis_pipeline() as pipe:
        with self.db_session() as dbsession:
            if session is None:  # pragma: no cover
                session = dbsession
            import_stations(session,
                            pipe,
                            filename,
                            CELL_FIELDS)


@celery_app.task(base=DatabaseTask, bind=True)
def import_latest_ocid_cells(self, diff=True, filename=None, session=None):
    url = self.app.settings['ichnaea']['ocid_url']
    apikey = self.app.settings['ichnaea']['ocid_apikey']
    if not url or not apikey:  # pragma: no cover
        return

    if filename is None:
        if diff:
            prev_hour = util.utcnow() - timedelta(hours=1)
            filename = prev_hour.strftime('cell_towers_diff-%Y%m%d%H.csv.gz')
        else:  # pragma: no cover
            filename = 'cell_towers.csv.gz'

    with closing(requests.get(url,
                              params={'apiKey': apikey,
                                      'filename': filename},
                              stream=True)) as r:
        with selfdestruct_tempdir() as d:
            path = os.path.join(d, filename)
            with open(path, 'wb') as f:
                for chunk in r.iter_content(chunk_size=2 ** 20):
                    f.write(chunk)
                    f.flush()

            with self.redis_pipeline() as pipe:
                with self.db_session() as dbsession:
                    if session is None:  # pragma: no cover
                        session = dbsession
                    import_stations(session,
                                    pipe,
                                    path,
                                    CELL_FIELDS)
