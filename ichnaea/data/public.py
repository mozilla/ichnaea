from datetime import timedelta
import os

import boto3
from sqlalchemy.sql import text

from ichnaea.config import (
    ASSET_BUCKET,
)
from ichnaea.models import (
    CellShard,
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

    def __call__(self, hourly=True, _bucket=None):
        if _bucket is None:  # pragma: no cover
            bucket = ASSET_BUCKET
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
        s3 = boto3.resource('s3')
        bucket = s3.Bucket(bucketname)
        obj = bucket.Object('export/' + os.path.split(path)[-1])
        obj.upload_file(path)
