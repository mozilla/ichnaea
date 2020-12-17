from collections import defaultdict, Counter
from csv import reader
from datetime import datetime, timedelta
import logging
import os

import boto3
import colander
from more_itertools import peekable
from zoneinfo import ZoneInfo
from sqlalchemy.sql import text
from sqlalchemy.orm import load_only

from ichnaea.cache import redis_pipeline
from ichnaea.conf import settings
from ichnaea.models import area_id, CellShard
from ichnaea.models.constants import CELL_MAX_RADIUS
from ichnaea import util


LOGGER = logging.getLogger(__name__)

_FIELD_NAMES = [
    "radio",
    "mcc",
    "net",
    "area",
    "cell",
    "unit",
    "lon",
    "lat",
    "range",
    "samples",
    "changeable",
    "created",
    "updated",
    "averageSignal",
]


def write_stations_to_csv(session, path, today, start_time=None, end_time=None):
    linesep = "\r\n"

    where = "lat IS NOT NULL AND lon IS NOT NULL"
    if start_time is not None and end_time is not None:
        where = where + ' AND modified >= "%s" AND modified < "%s"'
        fmt = "%Y-%m-%d %H:%M:%S"
        where = where % (start_time.strftime(fmt), end_time.strftime(fmt))
    else:
        # limit to cells modified in the last 12 months
        one_year = today - timedelta(days=365)
        where = where + ' AND modified >= "%s"' % one_year.strftime("%Y-%m-%d")

    header_row = ",".join(_FIELD_NAMES) + linesep

    tables = [shard.__tablename__ for shard in CellShard.shards().values()]
    stmt = """SELECT
    `cellid`,
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
WHERE %s AND `cellid` > :cellid
ORDER BY `cellid`
LIMIT :limit
"""

    with util.gzip_open(path, "w", compresslevel=5) as gzip_wrapper:
        with gzip_wrapper as gzip_file:
            gzip_file.write(header_row)
            for table in tables:
                table_stmt = text(stmt % (table, where))
                min_cellid = ""
                limit = 25000
                while True:
                    rows = session.execute(
                        table_stmt.bindparams(limit=limit, cellid=min_cellid)
                    ).fetchall()
                    if rows:
                        buf = "".join(row.cell_value + linesep for row in rows)
                        gzip_file.write(buf)
                        min_cellid = rows[-1].cellid
                    else:
                        break


class InvalidCSV(ValueError):
    """CSV does not appear to be a valid public cell export."""

    pass


def read_stations_from_csv(session, file_handle, redis_client, cellarea_queue):
    """
    Read stations from a public cell export CSV.

    :arg session: a database session
    :arg file_handle: an open file handle for the CSV data
    :arg redis_client: a Redis client
    :arg cellarea_queue: the DataQueue for updating cellarea IDs
    """
    # Avoid circular imports
    from ichnaea.data.tasks import update_cellarea, update_statregion

    csv_content = peekable(reader(file_handle))
    # UMTS was the original name for WCDMA stations
    radio_type = {"UMTS": "wcdma", "GSM": "gsm", "LTE": "lte", "": "Unknown"}

    counts = defaultdict(Counter)
    areas = set()
    areas_total = 0
    total = 0

    if not csv_content:
        LOGGER.warning("Nothing to process.")
        return

    first_row = csv_content.peek()
    if first_row == _FIELD_NAMES:
        # Skip the first row because it's a header row
        next(csv_content)
    else:
        LOGGER.warning("Expected header row, got data: %s", first_row)

    for row in csv_content:
        try:
            radio = radio_type[row[0]]
        except KeyError:
            raise InvalidCSV("Unknown radio type in row: %s" % row)

        if radio == "Unknown":
            LOGGER.warning("Skipping unknown radio: %s", row)
            continue

        try:
            data = {
                "radio": radio,
                "mcc": int(row[1]),
                "mnc": int(row[2]),
                "lac": int(row[3]),
                "cid": int(row[4]),
                "psc": int(row[5]) if row[5] else 0,
                "lon": float(row[6]),
                "lat": float(row[7]),
                # Some exported radiuses exceed the max and fail validation
                "radius": min(int(row[8]), CELL_MAX_RADIUS),
                "samples": int(row[9]),
                # row[10] is "changable", always 1 and not imported
                "created": datetime.fromtimestamp(int(row[11]), UTC),
                "modified": datetime.fromtimestamp(int(row[12]), UTC),
            }
            shard = CellShard.create(_raise_invalid=True, **data)
        except (colander.Invalid, ValueError) as e:
            if total == 0:
                # If the first row is invalid, it's likely the rest of the
                # file is, too--drop out here.
                raise InvalidCSV("first row %s is invalid: %s" % (row, e))
            else:
                LOGGER.warning("row %s is invalid: %s", row, e)
                continue

        # Is this station in the database?
        shard_type = shard.__class__
        existing = (
            session.query(shard_type)
            .filter(shard_type.cellid == shard.cellid)
            .options(load_only("modified"))
            .one_or_none()
        )

        if existing:
            if existing.modified < data["modified"]:
                # Update existing station with new data
                operation = "updated"
                existing.psc = shard.psc
                existing.lon = shard.lon
                existing.lat = shard.lat
                existing.radius = shard.radius
                existing.samples = shard.samples
                existing.created = shard.created
                existing.modified = shard.modified
            else:
                # Do nothing to existing station record
                operation = "found"
        else:
            # Add a new station record
            operation = "new"
            shard.min_lat = shard.lat
            shard.max_lat = shard.lat
            shard.min_lon = shard.lon
            shard.max_lon = shard.lon
            session.add(shard)

        counts[data["radio"]][operation] += 1

        # Process the cell area?
        if operation in {"new", "updated"}:
            areas.add(area_id(shard))

        # Process a chunk of stations, report on progress
        total += 1
        if total % 1000 == 0:
            session.commit()
            LOGGER.info("Processed %d stations", total)

        if areas and (len(areas) % 1000 == 0):
            session.commit()
            areas_total += len(areas)
            LOGGER.info("Processed %d station areas", areas_total)
            with redis_pipeline(redis_client) as pipe:
                cellarea_queue.enqueue(list(areas), pipe=pipe)
            update_cellarea.delay()
            areas = set()

    # Commit remaining station data
    session.commit()

    # Update the remaining cell areas
    if areas:
        areas_total += len(areas)
        with redis_pipeline(redis_client) as pipe:
            cellarea_queue.enqueue(list(areas), pipe=pipe)
        update_cellarea.delay()

    # Now that we've updated all the cell areas, we need to update the
    # statregion
    update_statregion.delay()

    # Summarize results
    LOGGER.info("Complete, processed %d station%s:", total, "" if total == 1 else "s")
    for radio_type, op_counts in sorted(counts.items()):
        LOGGER.info(
            "  %s: %d new, %d updated, %d already loaded",
            radio_type,
            op_counts["new"],
            op_counts["updated"],
            op_counts["found"],
        )
    if areas_total:
        LOGGER.info(
            "  %d station area%s updated", areas_total, "" if areas_total == 1 else "s"
        )


class CellExport(object):
    def __init__(self, task):
        self.task = task

    def __call__(self, hourly=True, _bucket=None):
        if _bucket is None:
            bucket = settings("asset_bucket")
        else:
            bucket = _bucket

        if not bucket:
            return

        now = util.utcnow()
        today = now.date()
        start_time = None
        end_time = None

        if hourly:
            end_time = now.replace(minute=0, second=0)
            file_time = end_time
            file_type = "diff"
            start_time = end_time - timedelta(hours=1)
        else:
            file_time = now.replace(hour=0, minute=0, second=0)
            file_type = "full"

        filename = "MLS-%s-cell-export-" % file_type
        filename = filename + file_time.strftime("%Y-%m-%dT%H0000.csv.gz")

        with util.selfdestruct_tempdir() as temp_dir:
            path = os.path.join(temp_dir, filename)
            with self.task.db_session(commit=False) as session:
                write_stations_to_csv(
                    session, path, today, start_time=start_time, end_time=end_time
                )
            self.write_stations_to_s3(path, bucket)

    def write_stations_to_s3(self, path, bucketname):
        s3 = boto3.resource("s3")
        bucket = s3.Bucket(bucketname)
        obj = bucket.Object("export/" + os.path.split(path)[-1])
        obj.upload_file(path)
