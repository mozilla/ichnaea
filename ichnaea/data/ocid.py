from contextlib import contextmanager, closing
import csv
from datetime import datetime, timedelta
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

from ichnaea.models import (
    Cell,
    CellArea,
    OCIDCell,
    Radio,
    StatCounter,
    StatKey,
)
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


def make_cell_export_dict(row):
    data = {
        'changeable': 1,
        'averageSignal': '',
    }
    indices = CELL_COLUMN_NAME_INDICES

    for field in CELL_FIELDS:
        pos = indices.get(field, None)
        if pos is not None:
            data[field] = row[pos]

    # Fix up specific entry formatting
    radio = row[indices['radio']]

    data['radio'] = radio.name.upper()
    data['created'] = row[indices['created']]
    data['updated'] = row[indices['modified']]
    data['samples'] = row[indices['total_measures']]
    return data


def make_ocid_cell_import_dict(row):

    def val(key, default, _type):
        if key in row and row[key] != '' and row[key] is not None:
            return _type(row[key])
        else:
            return default

    data = dict()

    data['created'] = datetime.fromtimestamp(
        val('created', 0, int)).replace(tzinfo=UTC)

    data['modified'] = datetime.fromtimestamp(
        val('updated', 0, int)).replace(tzinfo=UTC)

    data['lat'] = val('lat', None, float)
    data['lon'] = val('lon', None, float)

    try:
        data['radio'] = Radio[row['radio'].lower()]
    except KeyError:  # pragma: no cover
        data['radio'] = None

    for field in ('mcc', 'mnc', 'lac', 'cid', 'psc'):
        data[field] = val(field, None, int)

    data['range'] = int(val('range', 0, float))
    data['total_measures'] = val('samples', 0, int)
    data['changeable'] = val('changeable', True, bool)
    validated = OCIDCell.validate(data)
    if validated is None:
        return None
    for field in ('radio', 'mcc', 'mnc', 'lac', 'cid'):
        if validated[field] is None:
            return None
    return validated


def write_stations_to_csv(session, table, columns,
                          cond, path, make_dict, fields):
    with util.gzip_open(path, 'w') as gzip_file:
        writer = csv.DictWriter(gzip_file, fields, extrasaction='ignore')
        limit = 10000
        offset = 0
        # Write header row
        writer.writerow(CELL_HEADER_DICT)
        while True:
            query = (select(columns=columns).where(cond)
                                            .limit(limit)
                                            .offset(offset)
                                            .order_by(table.c.created))
            rows = session.execute(query).fetchall()
            if rows:
                writer.writerows([make_dict(row) for row in rows])
                offset += limit
            else:
                break


def write_stations_to_s3(path, bucketname):
    conn = boto.connect_s3()
    bucket = conn.get_bucket(bucketname)
    k = boto.s3.key.Key(bucket)
    k.key = 'export/' + os.path.split(path)[-1]
    k.set_contents_from_filename(path, reduced_redundancy=True)


def export_modified_cells(task, hourly=True, _bucket=None):
    if _bucket is None:  # pragma: no cover
        bucket = task.app.settings['ichnaea']['s3_assets_bucket']
    else:
        bucket = _bucket

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

    with selfdestruct_tempdir() as temp_dir:
        path = os.path.join(temp_dir, filename)
        with task.db_session(commit=False) as session:
            write_stations_to_csv(session, Cell.__table__, CELL_COLUMNS, cond,
                                  path, make_cell_export_dict, CELL_FIELDS)
        write_stations_to_s3(path, bucket)


def import_stations(session, pipe, filename, fields, update_area_task):
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

    with util.gzip_open(filename, 'r') as gzip_file:
        csv_reader = csv.DictReader(gzip_file, fields)
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
            update_area_task.delay(area_key, cell_type='ocid')


def import_ocid_cells(session, pipe, filename=None, update_area_task=None):
    import_stations(session, pipe, filename, CELL_FIELDS, update_area_task)


def import_latest_ocid_cells(task, diff=True, update_area_task=None,
                             _filename=None):
    url = task.app.settings['ichnaea']['ocid_url']
    apikey = task.app.settings['ichnaea']['ocid_apikey']
    if not url or not apikey:  # pragma: no cover
        return

    if _filename is None:
        if diff:
            prev_hour = util.utcnow() - timedelta(hours=1)
            _filename = prev_hour.strftime('cell_towers_diff-%Y%m%d%H.csv.gz')
        else:  # pragma: no cover
            _filename = 'cell_towers.csv.gz'

    with closing(requests.get(url,
                              params={'apiKey': apikey,
                                      'filename': _filename},
                              stream=True)) as r:
        with selfdestruct_tempdir() as temp_dir:
            path = os.path.join(temp_dir, _filename)
            with open(path, 'wb') as temp_file:
                for chunk in r.iter_content(chunk_size=2 ** 20):
                    temp_file.write(chunk)
                    temp_file.flush()

            with task.redis_pipeline() as pipe:
                with task.db_session() as session:
                    import_stations(session, pipe, path, CELL_FIELDS,
                                    update_area_task)
