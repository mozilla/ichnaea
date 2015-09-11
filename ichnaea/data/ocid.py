from contextlib import closing
import csv
from datetime import datetime, timedelta
import os

import boto
import requests
from sqlalchemy.sql import text

from ichnaea import geocalc
from ichnaea.models import (
    Cell,
    CellArea,
    OCIDCell,
    OCIDCellArea,
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
ORDER BY `radio`, `mcc`, `mnc`, `lac`, `cid`
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


class CellExport(object):

    def __init__(self, task):
        self.task = task
        self.settings = task.app.settings['assets']

    def __call__(self, hourly=True, _bucket=None):
        if _bucket is None:  # pragma: no cover
            bucket = self.settings['bucket']
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

        with util.selfdestruct_tempdir() as temp_dir:
            path = os.path.join(temp_dir, filename)
            with self.task.db_session(commit=False) as session:
                write_stations_to_csv(
                    session, path,
                    start_time=start_time, end_time=end_time)
            self.write_stations_to_s3(path, bucket)

    def write_stations_to_s3(self, path, bucketname):
        conn = boto.connect_s3()
        bucket = conn.get_bucket(bucketname)
        with closing(boto.s3.key.Key(bucket)) as key:
            key.key = 'export/' + os.path.split(path)[-1]
            key.set_contents_from_filename(path, reduced_redundancy=True)


class ImportBase(object):

    batch_size = 10000
    area_batch_size = 10

    def __init__(self, task, cell_type='ocid', update_area_task=None):
        self.task = task
        self.cell_type = cell_type
        self.update_area_task = update_area_task
        if cell_type == 'ocid':
            self.cell_model = OCIDCell
            self.area_model = OCIDCellArea
            self.stat_key = StatKey.unique_ocid_cell
        elif cell_type == 'cell':  # pragma: no cover
            self.cell_model = Cell
            self.area_model = CellArea
            self.stat_key = StatKey.unique_cell

    def make_import_dict(self, row):

        def row_value(row, key, default, _type):
            if key in row and row[key] not in (None, ''):
                return _type(row[key])
            return default

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
        if self.cell_type == 'ocid':
            data['changeable'] = row_value(row, 'changeable', True, bool)
        elif self.cell_type == 'cell':  # pragma: no cover
            data['max_lat'] = geocalc.latitude_add(
                data['lat'], data['lon'], data['range'])
            data['min_lat'] = geocalc.latitude_add(
                data['lat'], data['lon'], -data['range'])
            data['max_lon'] = geocalc.longitude_add(
                data['lat'], data['lon'], data['range'])
            data['min_lon'] = geocalc.longitude_add(
                data['lat'], data['lon'], -data['range'])

        validated = self.cell_model.validate(data)
        if validated is None:
            return None
        for field in ('radio', 'mcc', 'mnc', 'lac', 'cid'):
            if validated[field] is None:
                return None
        return validated

    def import_stations(self, session, pipe, filename):
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
            StatCounter(self.stat_key, today).incr(pipe, inserted_rows)
            if commit:
                session.commit()
            else:  # pragma: no cover
                session.flush()

        with util.gzip_open(filename, 'r') as gzip_wrapper:
            with gzip_wrapper as gzip_file:
                csv_reader = csv.DictReader(gzip_file, CELL_FIELDS)
                rows = []
                on_duplicate = (
                    'modified = values(modified), '
                    'total_measures = values(total_measures), '
                    'lat = values(lat), '
                    'lon = values(lon), '
                    'psc = values(psc), '
                    '`range` = values(`range`)')
                if self.cell_type == 'ocid':
                    on_duplicate += ', changeable = values(changeable)'
                elif self.cell_type == 'cell':  # pragma: no cover
                    on_duplicate += (
                        ', max_lat = values(max_lat)'
                        ', min_lat = values(min_lat)'
                        ', max_lon = values(max_lon)'
                        ', min_lon = values(min_lon)')

                ins = self.cell_model.__table__.insert(
                    mysql_on_duplicate=on_duplicate)

                for row in csv_reader:
                    # skip any header row
                    if csv_reader.line_num == 1 and \
                       'radio' in row.values():  # pragma: no cover
                        continue

                    data = self.make_import_dict(row)
                    if data is not None:
                        rows.append(data)
                        area_keys.add(self.area_model.to_hashkey(data))

                    if len(rows) == self.batch_size:  # pragma: no cover
                        commit_batch(ins, rows, commit=False)
                        rows = []

                if rows:
                    commit_batch(ins, rows)

        area_keys = list(area_keys)
        for i in range(0, len(area_keys), self.area_batch_size):
            area_batch = area_keys[i:i + self.area_batch_size]
            self.update_area_task.delay(area_batch, cell_type=self.cell_type)


class ImportExternal(ImportBase):

    def __init__(self, task, cell_type='ocid', update_area_task=None):
        super(ImportExternal, self).__init__(
            task, cell_type=cell_type, update_area_task=update_area_task)
        self.settings = self.task.app.settings['import:ocid']

    def __call__(self, diff=True, _filename=None):
        url = self.settings['url']
        apikey = self.settings['apikey']
        if not url or not apikey:  # pragma: no cover
            return

        if _filename is None:
            if diff:
                prev_hour = util.utcnow() - timedelta(hours=1)
                _filename = prev_hour.strftime(
                    'cell_towers_diff-%Y%m%d%H.csv.gz')
            else:  # pragma: no cover
                _filename = 'cell_towers.csv.gz'

        with util.selfdestruct_tempdir() as temp_dir:
            path = os.path.join(temp_dir, _filename)
            with open(path, 'wb') as temp_file:
                with closing(requests.get(url,
                                          params={'apiKey': apikey,
                                                  'filename': _filename},
                                          stream=True)) as req:

                    for chunk in req.iter_content(chunk_size=2 ** 20):
                        temp_file.write(chunk)
                        temp_file.flush()

                with self.task.redis_pipeline() as pipe:
                    with self.task.db_session() as session:
                        self.import_stations(session, pipe, path)


class ImportLocal(ImportBase):

    def __init__(self, task, session, pipe,
                 cell_type='ocid', update_area_task=None):
        super(ImportLocal, self).__init__(
            task, cell_type=cell_type, update_area_task=update_area_task)
        self.session = session
        self.pipe = pipe

    def __call__(self, filename=None):
        self.import_stations(self.session, self.pipe, filename)
