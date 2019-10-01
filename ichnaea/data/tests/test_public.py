import csv
import os
import re
from datetime import datetime, timedelta
from io import StringIO
from unittest import mock

import boto3
import pytest
from pytz import UTC
from sqlalchemy import func

from ichnaea.data.public import (
    read_stations_from_csv,
    write_stations_to_csv,
    InvalidCSV,
)
from ichnaea.data.tasks import cell_export_full, cell_export_diff
from ichnaea.models import Radio, CellArea, CellShard, RegionStat
from ichnaea.taskapp.config import configure_data
from ichnaea.tests.factories import CellShardFactory
from ichnaea import util


CELL_FIELDS = [
    "radio",
    "mcc",
    "mnc",
    "lac",
    "cid",
    "psc",
    "lon",
    "lat",
    "range",
    "samples",
    "changeable",
    "created",
    "updated",
    "averageSignal",
]


class FakeTask(object):
    def __init__(self, app):
        self.app = app


class TestExport(object):
    def test_local_export(self, celery, session):
        now = util.utcnow()
        today = now.date()
        long_ago = now - timedelta(days=367)
        cell_fixture_fields = ("radio", "cid", "lat", "lon", "mnc", "mcc", "lac")
        base_cell = CellShardFactory.build(radio=Radio.wcdma)
        cell_key = {
            "radio": Radio.wcdma,
            "mcc": base_cell.mcc,
            "mnc": base_cell.mnc,
            "lac": base_cell.lac,
        }
        cells = set()

        for cid in range(190, 200):
            cell = dict(cid=cid, lat=base_cell.lat, lon=base_cell.lon, **cell_key)
            CellShardFactory(**cell)
            cell["lat"] = "%.7f" % cell["lat"]
            cell["lon"] = "%.7f" % cell["lon"]

            cell["radio"] = "UMTS"
            cell_strings = [(field, str(value)) for (field, value) in cell.items()]
            cell_tuple = tuple(sorted(cell_strings))
            cells.add(cell_tuple)

        # add one incomplete / unprocessed cell
        CellShardFactory(cid=210, lat=None, lon=None, **cell_key)
        # add one really old cell
        CellShardFactory(
            cid=220,
            created=long_ago,
            modified=long_ago,
            last_seen=long_ago.date(),
            **cell_key,
        )
        session.commit()

        with util.selfdestruct_tempdir() as temp_dir:
            path = os.path.join(temp_dir, "export.csv.gz")
            write_stations_to_csv(session, path, today)

            with util.gzip_open(path, "r") as gzip_wrapper:
                with gzip_wrapper as gzip_file:
                    reader = csv.DictReader(gzip_file, CELL_FIELDS)

                    header = next(reader)
                    assert "area" in header.values()

                    exported_cells = set()
                    for exported_cell in reader:
                        exported_cell_filtered = [
                            (field, value)
                            for (field, value) in exported_cell.items()
                            if field in cell_fixture_fields
                        ]
                        exported_cell = tuple(sorted(exported_cell_filtered))
                        exported_cells.add(exported_cell)

                    assert cells == exported_cells

    def test_export_diff(self, celery, session):
        CellShardFactory.create_batch(10, radio=Radio.gsm)
        session.commit()
        pattern = re.compile(r"MLS-diff-cell-export-\d+-\d+-\d+T\d+0000\.csv\.gz")

        mock_conn = mock.MagicMock()
        mock_bucket = mock.MagicMock(name="bucket")
        mock_obj = mock.MagicMock()
        mock_conn.return_value.Bucket.return_value = mock_bucket
        mock_bucket.Object.return_value = mock_obj

        with mock.patch.object(boto3, "resource", mock_conn):
            cell_export_diff(_bucket="bucket")

        s3_key = mock_bucket.Object.call_args[0][0]
        assert pattern.search(s3_key)

        tmp_file = mock_obj.upload_file.call_args[0][0]
        assert pattern.search(tmp_file)

    def test_export_full(self, celery, session):
        now = util.utcnow()
        long_ago = now - timedelta(days=367)
        CellShardFactory.create_batch(10, radio=Radio.gsm)
        CellShardFactory(
            radio=Radio.gsm,
            created=long_ago,
            modified=long_ago,
            last_seen=long_ago.date(),
        )
        session.commit()
        pattern = re.compile(r"MLS-full-cell-export-\d+-\d+-\d+T000000\.csv\.gz")

        mock_conn = mock.MagicMock()
        mock_bucket = mock.MagicMock(name="bucket")
        mock_obj = mock.MagicMock()
        mock_conn.return_value.Bucket.return_value = mock_bucket
        mock_bucket.Object.return_value = mock_obj

        with mock.patch.object(boto3, "resource", mock_conn):
            cell_export_full(_bucket="bucket")

        s3_key = mock_bucket.Object.call_args[0][0]
        assert pattern.search(s3_key)

        tmp_file = mock_obj.upload_file.call_args[0][0]
        assert pattern.search(tmp_file)


@pytest.fixture
def cellarea_queue(redis_client):
    """Return the DataQueue for updaing CellAreas by ID."""
    return configure_data(redis_client)["update_cellarea"]


class TestImport:
    def test_unexpected_csv(self, session, redis_client, cellarea_queue):
        """An unexpected CSV input exits early."""

        csv = StringIO(
            """\
region,name
US,United States
UK,United Kingdom
"""
        )
        with pytest.raises(InvalidCSV):
            read_stations_from_csv(session, csv, redis_client, cellarea_queue)

    def test_new_stations(self, session, redis_client, cellarea_queue):
        """New stations are imported, creating cell areas and region stats."""
        csv = StringIO(
            """\
radio,mcc,net,area,cell,unit,lon,lat,range,samples,changeable,created,updated,averageSignal
UMTS,202,1,2120,12842,,23.4123167,38.8574351,0,6,1,1568220564,1570120316,
GSM,208,10,30014,20669,,2.5112670,46.5992450,0,78,1,1566307030,1570119413,
LTE,202,1,2120,12842,,23.4123167,38.8574351,0,6,1,1568220588,1570120328,
"""
        )
        read_stations_from_csv(session, csv, redis_client, cellarea_queue)

        # Check the details of the UMTS station
        umts = session.query(CellShard.shard_model(Radio.umts)).one()
        assert umts.mcc == 202
        assert umts.mnc == 1
        assert umts.lac == 2120
        assert umts.cid == 12842
        assert umts.lat == 38.8574351
        assert umts.lon == 23.4123167
        assert umts.max_lat == umts.lat
        assert umts.min_lat == umts.lat
        assert umts.max_lon == umts.lon
        assert umts.min_lon == umts.lon
        assert umts.radius == 0
        assert umts.samples == 6
        assert umts.created == datetime(2019, 9, 11, 16, 49, 24, tzinfo=UTC)
        assert umts.modified == datetime(2019, 10, 3, 16, 31, 56, tzinfo=UTC)
        assert umts.region == "GR"

        # Check the counts of the other station types
        gsm_model = CellShard.shard_model(Radio.gsm)
        assert session.query(func.count(gsm_model.cellid)).scalar() == 1
        lte_model = CellShard.shard_model(Radio.lte)
        assert session.query(func.count(lte_model.cellid)).scalar() == 1

        # New stations trigger the creation of new CellAreas
        cell_areas = session.query(CellArea).order_by(CellArea.areaid).all()
        area1, area2, area3 = cell_areas
        assert area1.areaid == (Radio.gsm, 208, 10, 30014)
        assert area2.areaid == (Radio.wcdma, 202, 1, 2120)
        assert area3.areaid == (Radio.lte, 202, 1, 2120)

        # New CellAreas trigger the creation of RegionStats
        stats = session.query(RegionStat).order_by("region").all()
        assert len(stats) == 2
        actual = [
            (stat.region, stat.gsm, stat.wcdma, stat.lte, stat.blue, stat.wifi)
            for stat in stats
        ]
        expected = [("FR", 1, 0, 0, 0, 0), ("GR", 0, 1, 1, 0, 0)]
        assert actual == expected

    def test_modified_station(self, session, redis_client, cellarea_queue):
        """A modified station updates existing records."""
        station_data = {
            "radio": Radio.umts,
            "mcc": 202,
            "mnc": 1,
            "lac": 2120,
            "cid": 12842,
            "lat": 38.85,
            "lon": 23.41,
            "min_lat": 38.7,
            "max_lat": 38.9,
            "min_lon": 23.4,
            "max_lon": 23.5,
            "radius": 1,
            "samples": 1,
            "created": datetime(2019, 1, 1, tzinfo=UTC),
            "modified": datetime(2019, 1, 1, tzinfo=UTC),
        }
        station = CellShard.create(_raise_invalid=True, **station_data)
        session.add(station)
        session.flush()

        csv = StringIO(
            """\
radio,mcc,net,area,cell,unit,lon,lat,range,samples,changeable,created,updated,averageSignal
UMTS,202,1,2120,12842,,23.4123167,38.8574351,0,6,1,1568220564,1570120316,
"""
        )
        read_stations_from_csv(session, csv, redis_client, cellarea_queue)

        # Check the details of the UMTS station
        umts = session.query(CellShard.shard_model(Radio.umts)).one()
        # New position, other details from import
        assert umts.lat == 38.8574351
        assert umts.lon == 23.4123167
        assert umts.radius == 0
        assert umts.samples == 6
        assert umts.created == datetime(2019, 9, 11, 16, 49, 24, tzinfo=UTC)
        assert umts.modified == datetime(2019, 10, 3, 16, 31, 56, tzinfo=UTC)
        # Other details unchanged
        assert umts.max_lat == station_data["max_lat"]
        assert umts.min_lat == station_data["min_lat"]
        assert umts.max_lon == station_data["max_lon"]
        assert umts.min_lon == station_data["min_lon"]
        assert umts.region == "GR"

        # A Modified station triggers the creation of a new CellArea
        cell_area = session.query(CellArea).order_by(CellArea.areaid).one()
        assert cell_area.areaid == (Radio.wcdma, 202, 1, 2120)

        # The new CellAreas triggers the creation of a RegionStat
        stat = session.query(RegionStat).order_by("region").one()
        assert stat.region == "GR"
        assert stat.wcdma == 1

    def test_outdated_station(self, session, redis_client, cellarea_queue):
        """An older statuon record does not update existing station records."""
        station_data = {
            "radio": Radio.umts,
            "mcc": 202,
            "mnc": 1,
            "lac": 2120,
            "cid": 12842,
            "lat": 38.85,
            "lon": 23.41,
            "radius": 1,
            "samples": 1,
            "created": datetime(2019, 1, 1, tzinfo=UTC),
            "modified": datetime(2019, 10, 7, tzinfo=UTC),
        }
        station = CellShard.create(_raise_invalid=True, **station_data)
        session.add(station)
        session.flush()

        csv = StringIO(
            """\
radio,mcc,net,area,cell,unit,lon,lat,range,samples,changeable,created,updated,averageSignal
UMTS,202,1,2120,12842,,23.4123167,38.8574351,0,6,1,1568220564,1570120316,
"""
        )
        read_stations_from_csv(session, csv, redis_client, cellarea_queue)

        # The existing station is unmodified
        umts = session.query(CellShard.shard_model(Radio.umts)).one()
        assert umts.lat == 38.85
        assert umts.lon == 23.41
        assert umts.created == datetime(2019, 1, 1, tzinfo=UTC)
        assert umts.modified == datetime(2019, 10, 7, tzinfo=UTC)

        # No CellAreas or RegionStats are generated
        assert session.query(func.count(CellArea.areaid)).scalar() == 0
        assert session.query(func.count(RegionStat.region)).scalar() == 0

    def test_unexpected_radio_halts(self, session, redis_client, cellarea_queue):
        """
        A row with an unexpected radio type halts processing of the CSV.

        The public CSV export is limited to a few types of radios, so an unexpected
        radio type suggests file corruption or other shenanigans.
        """
        # In row 3, 'WCDMA'is not a valid radio string
        csv = StringIO(
            """\
radio,mcc,net,area,cell,unit,lon,lat,range,samples,changeable,created,updated,averageSignal
UMTS,202,1,2120,12842,,23.4123167,38.8574351,0,6,1,1568220564,1570120316,
WCDMA,203,1,2120,12842,,23.4123167,38.8574351,0,6,1,1568220564,1570120316,
GSM,208,10,30014,20669,,2.5112670,46.5992450,0,78,1,1566307030,1570119413,
"""
        )
        with pytest.raises(InvalidCSV):
            read_stations_from_csv(session, csv, redis_client, cellarea_queue)

        # Only the station before the error is loaded
        umts = session.query(CellShard.shard_model(Radio.umts)).one()
        assert umts.lat == 38.8574351
        assert umts.lon == 23.4123167
        gsm_model = CellShard.shard_model(Radio.gsm)
        assert session.query(func.count(gsm_model.cellid)).scalar() == 0
        assert session.query(func.count(CellArea.areaid)).scalar() == 1
        assert session.query(func.count(RegionStat.region)).scalar() == 1

    def test_empty_radio_skipped(self, session, redis_client, cellarea_queue):
        """
        A empty string for the radio type causes the row to be skipped.

        The public CSV export encodes an unexpected radio type from the database
        as an empty string. We can't determine what radio type was expected.
        """
        # In row 3, the radio is an empty string
        csv = StringIO(
            """\
radio,mcc,net,area,cell,unit,lon,lat,range,samples,changeable,created,updated,averageSignal
UMTS,202,1,2120,12842,,23.4123167,38.8574351,0,6,1,1568220564,1570120316,
,203,1,2120,12842,,23.4123167,38.8574351,0,6,1,1568220564,1570120316,
GSM,208,10,30014,20669,,2.5112670,46.5992450,0,78,1,1566307030,1570119413,
"""
        )
        read_stations_from_csv(session, csv, redis_client, cellarea_queue)

        # The empty radio row is skipped, but the following row is processed.
        umts = session.query(CellShard.shard_model(Radio.umts)).one()
        assert umts.lat == 38.8574351
        assert umts.lon == 23.4123167
        gsm_model = CellShard.shard_model(Radio.gsm)
        assert session.query(func.count(gsm_model.cellid)).scalar() == 1
        assert session.query(func.count(CellArea.areaid)).scalar() == 2
        assert session.query(func.count(RegionStat.region)).scalar() == 2

    def test_invalid_row_skipped(self, session, redis_client, cellarea_queue):
        """A row that fails validation is skipped."""
        # In GSM row, the longitude 202.5 is greater than max of 180
        csv = StringIO(
            """\
radio,mcc,net,area,cell,unit,lon,lat,range,samples,changeable,created,updated,averageSignal
UMTS,202,1,2120,12842,,23.4123167,38.8574351,0,6,1,1568220564,1570120316,
GSM,208,10,30014,20669,,202.5,46.5992450,0,78,1,1566307030,1570119413,
LTE,202,1,2120,12842,,23.4123167,38.8574351,0,6,1,1568220588,1570120328,
"""
        )
        read_stations_from_csv(session, csv, redis_client, cellarea_queue)

        # The invalid GSM row is skipped
        gsm_model = CellShard.shard_model(Radio.gsm)
        assert session.query(func.count(gsm_model.cellid)).scalar() == 0

        # The valid UMTS and LTE rows are processed, and in the same region
        umts_model = CellShard.shard_model(Radio.umts)
        lte_model = CellShard.shard_model(Radio.lte)
        assert session.query(func.count(umts_model.cellid)).scalar() == 1
        assert session.query(func.count(lte_model.cellid)).scalar() == 1
        assert session.query(func.count(CellArea.areaid)).scalar() == 2
        assert session.query(func.count(RegionStat.region)).scalar() == 1

    def test_bad_data_skipped(self, session, redis_client, cellarea_queue):
        """A row that has invalid data (like a string for a number) is skipped."""
        # In GSM row, the mcc field should be a number, not a string
        csv = StringIO(
            """\
radio,mcc,net,area,cell,unit,lon,lat,range,samples,changeable,created,updated,averageSignal
UMTS,202,1,2120,12842,,23.4123167,38.8574351,0,6,1,1568220564,1570120316,
GSM,"MCC",10,30014,20669,,2.5112670,46.5992450,0,78,1,1566307030,1570119413,
LTE,202,1,2120,12842,,23.4123167,38.8574351,0,6,1,1568220588,1570120328,
"""
        )
        read_stations_from_csv(session, csv, redis_client, cellarea_queue)

        # The invalid GSM row is skipped
        gsm_model = CellShard.shard_model(Radio.gsm)
        assert session.query(func.count(gsm_model.cellid)).scalar() == 0

        # The valid UMTS and LTE rows are processed, and in the same region
        umts_model = CellShard.shard_model(Radio.umts)
        lte_model = CellShard.shard_model(Radio.lte)
        assert session.query(func.count(umts_model.cellid)).scalar() == 1
        assert session.query(func.count(lte_model.cellid)).scalar() == 1
        assert session.query(func.count(CellArea.areaid)).scalar() == 2
        assert session.query(func.count(RegionStat.region)).scalar() == 1
