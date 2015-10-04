from contextlib import closing
import csv
from datetime import datetime, timedelta
from functools import partial
import os

import boto
import requests
from sqlalchemy.sql import text

from ichnaea import geocalc
from ichnaea.models import (
    encode_cellarea,
    Cell,
    CellOCID,
    Radio,
    StatCounter,
    StatKey,
)
from ichnaea import util

CELL_POS = {
    'radio': 0,
    'mcc': 1,
    'mnc': 2,
    'lac': 3,
    'cid': 4,
    'psc': 5,
    'lon': 6,
    'lat': 7,
    'range': 8,
    'samples': 9,
    'changeable': 10,
    'created': 11,
    'updated': 12,
    'averageSignal': 13,
}


def write_stations_to_csv(session, path, start_time=None, end_time=None):
    where = 'radio != 1 AND lat IS NOT NULL AND lon IS NOT NULL'
    if None not in (start_time, end_time):
        where = where + ' AND modified >= "%s" AND modified < "%s"'
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

    def __init__(self, task, cell_type='ocid'):
        self.task = task
        self.cell_type = cell_type
        if cell_type == 'ocid':
            self.cell_model = CellOCID
            self.area_queue = task.app.data_queues['update_cellarea_ocid']
            self.stat_key = StatKey.unique_cell_ocid
        elif cell_type == 'cell':  # pragma: no cover
            self.cell_model = Cell
            self.area_queue = task.app.data_queues['update_cellarea']
            self.stat_key = StatKey.unique_cell

        self.import_spec = [
            ('mcc', 1, None, int),
            ('mnc', 2, None, int),
            ('lac', 3, None, int),
            ('cid', 4, None, int),
            ('psc', 5, None, int),
            ('lon', 6, None, float),
            ('lat', 7, None, float),
            ('created', 11, 0, int),
            ('modified', 12, 0, int),
        ]
        if self.cell_type == 'ocid':
            self.import_spec.extend([
                ('radius', 8, 0, int),
                ('samples', 9, 0, int),
            ])
        else:  # pragma: no cover
            self.import_spec.extend([
                ('range', 8, 0, int),
                ('total_measures', 9, 0, int),
            ])

    @staticmethod
    def make_import_dict(validate, radius_field, import_spec, row):
        data = {}

        # parse radio field
        radio = row[0].lower()
        if radio == 'cdma':  # pragma: no cover
            return None
        if radio == 'umts':
            radio = 'wcdma'
        try:
            data['radio'] = Radio[radio]
        except KeyError:  # pragma: no cover
            return None

        for field, pos, default, _type in import_spec:
            value = row[pos]
            if value is None or value == '':
                data[field] = default
            else:
                data[field] = _type(value)

        data['created'] = datetime.utcfromtimestamp(data['created'])
        data['modified'] = datetime.utcfromtimestamp(data['modified'])
        data['max_lat'], data['min_lat'], \
            data['max_lon'], data['min_lon'] = geocalc.bbox(
                data['lat'], data['lon'], data[radius_field])

        validated = validate(data)
        if validated is None:
            return None
        for field in ('country', 'cellid',
                      'radio', 'mcc', 'mnc', 'lac', 'cid'):
            if validated[field] is None:
                return None

        return validated

    def import_stations(self, session, pipe, filename):
        today = util.utcnow().date()

        on_duplicate = (
            'modified = values(modified)'
            ', lat = values(lat)'
            ', lon = values(lon)'
            ', psc = values(psc)'
            ', max_lat = values(max_lat)'
            ', min_lat = values(min_lat)'
            ', max_lon = values(max_lon)'
            ', min_lon = values(min_lon)'
        )
        if self.cell_type == 'ocid':
            radius_field = 'radius'
            on_duplicate += (
                ', `radius` = values(`radius`)'
                ', `samples` = values(`samples`)'
            )
        elif self.cell_type == 'cell':  # pragma: no cover
            radius_field = 'range'
            on_duplicate += (
                ', `range` = values(`range`)'
                ', `total_measures` = values(`total_measures`)'
            )

        table_insert = self.cell_model.__table__.insert(
            mysql_on_duplicate=on_duplicate)

        def commit_batch(rows):
            result = session.execute(table_insert, rows)
            count = result.rowcount
            # apply trick to avoid querying for existing rows,
            # MySQL claims 1 row for an inserted row, 2 for an updated row
            inserted_rows = 2 * len(rows) - count
            changed_rows = count - len(rows)
            assert inserted_rows + changed_rows == len(rows)
            StatCounter(self.stat_key, today).incr(pipe, inserted_rows)

        areaids = set()

        with util.gzip_open(filename, 'r') as gzip_wrapper:
            with gzip_wrapper as gzip_file:
                csv_reader = csv.reader(gzip_file)
                parse_row = partial(self.make_import_dict,
                                    self.cell_model.validate,
                                    radius_field,
                                    self.import_spec)
                rows = []
                for row in csv_reader:
                    # skip any header row
                    if (csv_reader.line_num == 1 and
                            row[0] == 'radio'):  # pragma: no cover
                        continue

                    data = parse_row(row)
                    if data is not None:
                        rows.append(data)
                        areaids.add((int(data['radio']), data['mcc'],
                                    data['mnc'], data['lac']))

                    if len(rows) == self.batch_size:  # pragma: no cover
                        commit_batch(rows)
                        session.flush()
                        rows = []

                if rows:
                    commit_batch(rows)

        self.area_queue.enqueue(
            [encode_cellarea(*id_) for id_ in areaids], json=False)


class ImportExternal(ImportBase):

    def __init__(self, task, cell_type='ocid'):
        super(ImportExternal, self).__init__(task, cell_type=cell_type)
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

    def __init__(self, task, session, pipe, cell_type='ocid'):
        super(ImportLocal, self).__init__(task, cell_type=cell_type)
        self.session = session
        self.pipe = pipe

    def __call__(self, filename=None):
        self.import_stations(self.session, self.pipe, filename)
