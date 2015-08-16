from contextlib import contextmanager, closing
import csv
from datetime import datetime, timedelta
import os
import shutil
import tempfile

import boto
import requests
from sqlalchemy.sql import text

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

# Map our internal names to the public export names
CELL_HEADER_DICT = dict([(field, field) for field in CELL_FIELDS])
CELL_HEADER_DICT['mnc'] = 'net'
CELL_HEADER_DICT['lac'] = 'area'
CELL_HEADER_DICT['cid'] = 'cell'
CELL_HEADER_DICT['psc'] = 'unit'


@contextmanager
def selfdestruct_tempdir():
    base_path = tempfile.mkdtemp()
    try:
        yield base_path
    finally:
        shutil.rmtree(base_path)


def write_stations_to_csv(session, path, start_time=None, end_time=None):
    if None in (start_time, end_time):
        where = 'lat IS NOT NULL AND lon IS NOT NULL'
    else:
        where = ('lat IS NOT NULL AND lon IS NOT NULL AND '
                 'modified >= "%s" AND modified < "%s"')
        fmt = '%Y-%m-%d %H:%M:%S'
        where = where % (start_time.strftime(fmt), end_time.strftime(fmt))

    header_row = [
        'radio', 'mcc', 'net', 'area', 'cell', 'unit',
        'lon', 'lat', 'range', 'samples', 'changeable',
        'created', 'updated', 'averageSignal',
    ]
    header_row = ','.join(header_row) + '\n'

    table = Cell.__tablename__
    stmt = """SELECT
    CONCAT_WS(",",
        CASE radio
            WHEN 0 THEN "GSM"
            WHEN 1 THEN "CDMA"
            WHEN 2 THEN "UMTS"
            WHEN 3 THEN "LTE"
            ELSE ""
        END,
        `mcc`,
        `mnc`,
        `lac`,
        `cid`,
        COALESCE(`psc`, ""),
        ROUND(`lon`, 7),
        ROUND(`lat`, 7),
        COALESCE(`range`, "0"),
        COALESCE(`total_measures`, "0"),
        "1",
        COALESCE(UNIX_TIMESTAMP(`created`), ""),
        COALESCE(UNIX_TIMESTAMP(`modified`), ""),
        ""
    ) AS `cell_value`
FROM %s
WHERE %s
ORDER BY `created`
LIMIT :l
OFFSET :o
""" % (table, where)
    stmt = text(stmt)

    limit = 10000
    offset = 0
    with util.gzip_open(path, 'w', compresslevel=5) as gzip_wrapper:
        with gzip_wrapper as gzip_file:
            gzip_file.write(header_row)
            while True:
                rows = session.execute(
                    stmt.bindparams(o=offset, l=limit)).fetchall()
                if rows:
                    buf = '\r\n'.join([row.cell_value for row in rows])
                    if buf:
                        buf += '\r\n'
                    gzip_file.write(buf)
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
        bucket = task.app.settings['assets']['bucket']
    else:
        bucket = _bucket

    if not bucket:  # pragma: no cover
        return

    now = util.utcnow()
    start_time = None
    end_time = None

    if hourly:
        end_time = now.replace(minute=0, second=0)
        file_time = end_time
        file_type = 'diff'
        start_time = end_time - timedelta(hours=1)
    else:
        file_time = now.replace(hour=0, minute=0, second=0)
        file_type = 'full'

    filename = 'MLS-%s-cell-export-' % file_type
    filename = filename + file_time.strftime('%Y-%m-%dT%H0000.csv.gz')

    with selfdestruct_tempdir() as temp_dir:
        path = os.path.join(temp_dir, filename)
        with task.db_session(commit=False) as session:
            write_stations_to_csv(
                session, path,
                start_time=start_time, end_time=end_time)
        write_stations_to_s3(path, bucket)


def row_value(row, key, default, _type):
    if key in row and row[key] not in (None, ''):
        return _type(row[key])
    return default


def make_ocid_cell_import_dict(row):
    data = {}
    data['created'] = datetime.fromtimestamp(
        row_value(row, 'created', 0, int))

    data['modified'] = datetime.fromtimestamp(
        row_value(row, 'updated', 0, int))

    data['lat'] = row_value(row, 'lat', None, float)
    data['lon'] = row_value(row, 'lon', None, float)

    try:
        radio = row['radio'].lower()
        if radio == 'umts':
            radio = 'wcdma'
        data['radio'] = Radio[radio]
    except KeyError:  # pragma: no cover
        return None

    for field in ('mcc', 'mnc', 'lac', 'cid', 'psc'):
        data[field] = row_value(row, field, None, int)

    data['range'] = int(row_value(row, 'range', 0, float))
    data['total_measures'] = row_value(row, 'samples', 0, int)
    data['changeable'] = row_value(row, 'changeable', True, bool)
    validated = OCIDCell.validate(data)
    if validated is None:
        return None
    for field in ('radio', 'mcc', 'mnc', 'lac', 'cid'):
        if validated[field] is None:
            return None
    return validated


def import_stations(session, pipe, filename, fields, update_area_task):
    today = util.utcnow().date()
    area_keys = set()

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

    with util.gzip_open(filename, 'r') as gzip_wrapper:
        with gzip_wrapper as gzip_file:
            csv_reader = csv.DictReader(gzip_file, fields)
            batch = 10000
            rows = []
            ins = OCIDCell.__table__.insert(
                mysql_on_duplicate=(
                    'changeable = values(changeable), '
                    'modified = values(modified), '
                    'total_measures = values(total_measures), '
                    'lat = values(lat), '
                    'lon = values(lon), '
                    'psc = values(psc), '
                    '`range` = values(`range`)'))

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

    area_keys = list(area_keys)
    batch_size = 10
    for i in range(0, len(area_keys), batch_size):
        area_batch = area_keys[i:i + batch_size]
        update_area_task.delay(area_batch, cell_type='ocid')


def import_ocid_cells(session, pipe, filename=None, update_area_task=None):
    import_stations(session, pipe, filename, CELL_FIELDS, update_area_task)


def import_latest_ocid_cells(task, diff=True, update_area_task=None,
                             _filename=None):
    url = task.app.settings['import:ocid']['url']
    apikey = task.app.settings['import:ocid']['apikey']
    if not url or not apikey:  # pragma: no cover
        return

    if _filename is None:
        if diff:
            prev_hour = util.utcnow() - timedelta(hours=1)
            _filename = prev_hour.strftime('cell_towers_diff-%Y%m%d%H.csv.gz')
        else:  # pragma: no cover
            _filename = 'cell_towers.csv.gz'

    with selfdestruct_tempdir() as temp_dir:
        path = os.path.join(temp_dir, _filename)
        with open(path, 'wb') as temp_file:
            with closing(requests.get(url,
                                      params={'apiKey': apikey,
                                              'filename': _filename},
                                      stream=True)) as req:

                for chunk in req.iter_content(chunk_size=2 ** 20):
                    temp_file.write(chunk)
                    temp_file.flush()

            with task.redis_pipeline() as pipe:
                with task.db_session() as session:
                    import_stations(session, pipe, path, CELL_FIELDS,
                                    update_area_task)
