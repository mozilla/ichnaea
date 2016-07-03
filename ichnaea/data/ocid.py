from collections import defaultdict
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
    CellShard,
    CellShardOCID,
    Radio,
    StatCounter,
    StatKey,
)
from ichnaea import util


def write_stations_to_csv(session, path, today,
                          start_time=None, end_time=None):
    where = 'radio != 1 AND lat IS NOT NULL AND lon IS NOT NULL'
    if start_time is not None and end_time is not None:
        where = where + ' AND modified >= "%s" AND modified < "%s"'
        fmt = '%Y-%m-%d %H:%M:%S'
        where = where % (start_time.strftime(fmt), end_time.strftime(fmt))
    else:
        # limit to cells modified in the last 12 months
        one_year = today - timedelta(days=365)
        where = where + ' AND modified >= "%s"' % one_year.strftime('%Y-%m-%d')

    header_row = [
        'radio', 'mcc', 'net', 'area', 'cell', 'unit',
        'lon', 'lat', 'range', 'samples', 'changeable',
        'created', 'updated', 'averageSignal',
    ]
    header_row = ','.join(header_row) + '\n'

    tables = [shard.__tablename__ for shard in CellShard.shards().values()]
    stmt = '''SELECT
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
        COALESCE(`radius`, "0"),
        COALESCE(`samples`, "0"),
        "1",
        COALESCE(UNIX_TIMESTAMP(`created`), ""),
        COALESCE(UNIX_TIMESTAMP(`modified`), ""),
        ""
    ) AS `cell_value`
FROM %s
WHERE %s
ORDER BY `cellid`
LIMIT :l
OFFSET :o
'''

    with util.gzip_open(path, 'w', compresslevel=5) as gzip_wrapper:
        with gzip_wrapper as gzip_file:
            gzip_file.write(header_row)
            for table in tables:
                table_stmt = text(stmt % (table, where))
                offset = 0
                limit = 25000
                while True:
                    rows = session.execute(
                        table_stmt.bindparams(o=offset, l=limit)).fetchall()
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
        today = now.date()
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
                    session, path, today,
                    start_time=start_time, end_time=end_time)
            self.write_stations_to_s3(path, bucket)

    def write_stations_to_s3(self, path, bucketname):
        conn = boto.connect_s3()
        bucket = conn.get_bucket(bucketname, validate=False)
        with closing(boto.s3.key.Key(bucket)) as key:
            key.key = 'export/' + os.path.split(path)[-1]
            key.set_contents_from_filename(path, reduced_redundancy=True)


class ImportBase(object):

    batch_size = 10000
    import_spec = [
        ('mcc', 1, None, int),
        ('mnc', 2, None, int),
        ('lac', 3, None, int),
        ('cid', 4, None, int),
        ('psc', 5, None, int),
        ('lon', 6, None, float),
        ('lat', 7, None, float),
        ('radius', 8, 0, int),
        ('samples', 9, 0, int),
        # skip changeable
        ('created', 11, 0, int),
        ('modified', 12, 0, int),
        # skip averageSignal
    ]

    def __init__(self, task, cell_type='ocid'):
        self.task = task
        self.cell_type = cell_type
        if cell_type == 'ocid':
            self.cell_model = CellShardOCID
            self.area_queue = task.app.data_queues['update_cellarea_ocid']
            self.stat_key = StatKey.unique_cell_ocid
        elif cell_type == 'cell':
            self.cell_model = CellShard
            self.area_queue = task.app.data_queues['update_cellarea']
            self.stat_key = StatKey.unique_cell

    @staticmethod
    def make_import_dict(validate, import_spec, row):
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
        if (data['radius'] is not None and
                data['lat'] is not None and
                data['lon'] is not None):
            data['max_lat'], data['min_lat'], \
                data['max_lon'], data['min_lon'] = geocalc.bbox(
                    data['lat'], data['lon'], data['radius'])

        validated = validate(data)
        if validated is None:
            return None
        for field in ('region', 'cellid',
                      'radio', 'mcc', 'mnc', 'lac', 'cid'):
            if validated[field] is None:
                return None

        return validated

    def import_stations(self, pipe, session, filename):
        today = util.utcnow().date()
        shards = self.cell_model.shards()

        on_duplicate = (
            '`modified` = values(`modified`)'
            ', `lat` = values(`lat`)'
            ', `lon` = values(`lon`)'
            ', `psc` = values(`psc`)'
            ', `max_lat` = values(`max_lat`)'
            ', `min_lat` = values(`min_lat`)'
            ', `max_lon` = values(`max_lon`)'
            ', `min_lon` = values(`min_lon`)'
            ', `radius` = values(`radius`)'
            ', `samples` = values(`samples`)'
        )

        def commit_batch(rows):
            all_inserted_rows = 0
            for shard_id, shard_rows in rows.items():
                table_insert = shards[shard_id].__table__.insert(
                    mysql_on_duplicate=on_duplicate)

                result = session.execute(table_insert, shard_rows)
                count = result.rowcount
                # apply trick to avoid querying for existing rows,
                # MySQL claims 1 row for an inserted row, 2 for an updated row
                inserted_rows = 2 * len(shard_rows) - count
                changed_rows = count - len(shard_rows)
                assert inserted_rows + changed_rows == len(shard_rows)
                all_inserted_rows += inserted_rows
            StatCounter(self.stat_key, today).incr(pipe, all_inserted_rows)

        areaids = set()

        with util.gzip_open(filename, 'r') as gzip_wrapper:
            with gzip_wrapper as gzip_file:
                cell_model = self.cell_model
                csv_reader = csv.reader(gzip_file)
                parse_row = partial(self.make_import_dict,
                                    self.cell_model.validate,
                                    self.import_spec)

                rows = defaultdict(list)
                row_count = 0
                for row in csv_reader:
                    # skip any header row
                    if (csv_reader.line_num == 1 and
                            row[0] == 'radio'):  # pragma: no cover
                        continue

                    data = parse_row(row)
                    if data is not None:
                        rows[cell_model.shard_id(data['radio'])].append(data)
                        row_count += 1
                        areaids.add((int(data['radio']), data['mcc'],
                                    data['mnc'], data['lac']))

                    if row_count == self.batch_size:  # pragma: no cover
                        commit_batch(rows)
                        session.flush()
                        rows = defaultdict(list)
                        row_count = 0

                if rows:
                    commit_batch(rows)

        self.area_queue.enqueue(
            [encode_cellarea(*id_) for id_ in areaids])


class ImportExternal(ImportBase):

    def __init__(self, task, cell_type='ocid'):
        super(ImportExternal, self).__init__(task, cell_type=cell_type)
        self.settings = self.task.app.settings.get('import:ocid', {})

    def __call__(self, _filename=None):
        url = self.settings.get('url')
        apikey = self.settings.get('apikey')
        if not url or not apikey:  # pragma: no cover
            return

        if _filename is None:
            prev_hour = util.utcnow() - timedelta(hours=1)
            _filename = prev_hour.strftime(
                'cell_towers_diff-%Y%m%d%H.csv.gz')

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
                        self.import_stations(pipe, session, path)


class ImportLocal(ImportBase):

    def __init__(self, task, cell_type='ocid'):
        super(ImportLocal, self).__init__(task, cell_type=cell_type)

    def __call__(self, pipe, session, filename=None):
        self.import_stations(pipe, session, filename)
