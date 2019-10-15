from datetime import timedelta

from ichnaea.data.tasks import update_cellarea
from ichnaea.models import area_id, encode_cellarea, CellArea, Radio
from ichnaea.tests.factories import CellAreaFactory, CellShardFactory
from ichnaea import util


class TestArea(object):

    area_model = CellArea
    area_factory = CellAreaFactory
    cell_factory = CellShardFactory
    task = update_cellarea

    def area_queue(self, celery):
        return celery.data_queues["update_cellarea"]

    def test_empty(self, celery, session):
        self.task.delay().get()

    def test_new(self, celery, session):
        cell = self.cell_factory()
        session.flush()

        areaid = encode_cellarea(cell.radio, cell.mcc, cell.mnc, cell.lac)
        self.area_queue(celery).enqueue([areaid])
        self.task.delay().get()

        area = session.query(self.area_model).one()
        assert area.lat == cell.lat
        assert area.lon == cell.lon
        assert area.radius == 0
        assert area.region == "GB"
        assert area.avg_cell_radius == cell.radius
        assert area.num_cells == 1
        assert area.last_seen == cell.last_seen

    def test_remove(self, celery, session):
        area = self.area_factory()
        session.flush()

        areaid = encode_cellarea(*area.areaid)
        self.area_queue(celery).enqueue([areaid])
        self.task.delay().get()
        assert session.query(self.area_model).count() == 0

    def test_update(self, celery, session):
        today = util.utcnow().date()
        yesterday = today - timedelta(days=1)
        area = self.area_factory(
            num_cells=2, radius=500, avg_cell_radius=100, last_seen=yesterday
        )
        cell = self.cell_factory(
            lat=area.lat,
            lon=area.lon,
            radius=200,
            last_seen=today,
            radio=area.radio,
            mcc=area.mcc,
            mnc=area.mnc,
            lac=area.lac,
        )
        self.cell_factory(
            lat=area.lat,
            lon=area.lon,
            radius=300,
            last_seen=yesterday,
            radio=area.radio,
            mcc=area.mcc,
            mnc=area.mnc,
            lac=area.lac,
        )
        session.commit()

        areaid = encode_cellarea(*area.areaid)
        self.area_queue(celery).enqueue([areaid])
        self.task.delay().get()

        session.refresh(area)
        assert area.lat == cell.lat
        assert area.lon == cell.lon
        assert area.radius == 0
        assert area.region == "GB"
        assert area.avg_cell_radius == 250
        assert area.num_cells == 2
        assert area.last_seen == today

    def test_update_incomplete_cell(self, celery, session):
        area = self.area_factory(radius=500)
        area_key = {
            "radio": area.radio,
            "mcc": area.mcc,
            "mnc": area.mnc,
            "lac": area.lac,
        }
        cell = self.cell_factory(lat=area.lat + 0.0002, lon=area.lon, **area_key)
        self.cell_factory(lat=None, lon=None, **area_key)
        self.cell_factory(
            lat=area.lat, lon=area.lon, max_lat=None, min_lon=None, **area_key
        )
        session.commit()

        areaid = encode_cellarea(*area.areaid)
        self.area_queue(celery).enqueue([areaid])
        self.task.delay().get()

        session.refresh(area)
        assert round(area.lat, 7) == round(cell.lat - 0.0001, 7)
        assert round(area.lon, 7) == round(cell.lon, 7)
        assert area.num_cells == 2

    def test_region(self, celery, session):
        cell = self.cell_factory(
            radio=Radio.gsm,
            mcc=425,
            mnc=1,
            lac=1,
            cid=1,
            lat=32.2,
            lon=35.0,
            radius=10000,
            region="XW",
        )
        self.cell_factory(
            radio=cell.radio,
            mcc=cell.mcc,
            mnc=cell.mnc,
            lac=cell.lac,
            cid=2,
            lat=32.2,
            lon=34.9,
            radius=10000,
            region="IL",
        )
        session.flush()

        self.area_queue(celery).enqueue([area_id(cell)])
        self.task.delay().get()

        area = session.query(self.area_model).one()
        assert area.region == "IL"

    def test_region_outside(self, celery, session):
        cell = self.cell_factory(
            radio=Radio.gsm,
            mcc=310,
            mnc=1,
            lac=1,
            cid=1,
            lat=18.33,
            lon=-64.9,
            radius=10000,
            region="PR",
        )
        self.cell_factory(
            radio=cell.radio,
            mcc=cell.mcc,
            mnc=cell.mnc,
            lac=cell.lac,
            cid=2,
            lat=18.34,
            lon=-64.9,
            radius=10000,
            region="PR",
        )
        self.cell_factory(
            radio=cell.radio,
            mcc=cell.mcc,
            mnc=cell.mnc,
            lac=cell.lac,
            cid=3,
            lat=35.8,
            lon=-83.1,
            radius=10000,
            region="US",
        )
        session.flush()

        self.area_queue(celery).enqueue([area_id(cell)])
        self.task.delay().get()

        area = session.query(self.area_model).one()
        assert area.region == "PR"

    def test_region_outside_tie(self, celery, session):
        cell = self.cell_factory(
            radio=Radio.gsm,
            mcc=310,
            mnc=1,
            lac=1,
            cid=1,
            lat=18.33,
            lon=-64.9,
            radius=10000,
            region="PR",
        )
        self.cell_factory(
            radio=cell.radio,
            mcc=cell.mcc,
            mnc=cell.mnc,
            lac=cell.lac,
            cid=2,
            lat=18.34,
            lon=-64.9,
            radius=10000,
            region="PR",
        )
        session.flush()

        self.area_queue(celery).enqueue([area_id(cell)])
        self.task.delay().get()

        area = session.query(self.area_model).one()
        assert area.region == "PR"

    def test_region_all_none(self, celery, session):
        """If all cell regions are None, the area region is None."""

        # Sardinia, in Mediterranean, not identified as part of Italy
        cell = self.cell_factory(
            radio=Radio.wcdma,
            mcc=204,
            mnc=4,
            lac=35051,
            cid=1018429,
            lat=40.18,
            lon=9.59,
            radius=10,
            region=None,
        )
        assert cell.region is None
        cell2 = self.cell_factory(
            radio=cell.radio,
            mcc=cell.mcc,
            mnc=cell.mnc,
            lac=cell.lac,
            cid=cell.cid + 1,
            lat=cell.lat + 0.1,
            lon=cell.lon + 0.1,
            radius=10,
            region=None,
        )
        assert cell2.region is None
        session.flush()

        self.area_queue(celery).enqueue([area_id(cell)])
        self.task.delay().get()

        area = session.query(self.area_model).one()
        assert area.region is None

    def test_region_null_tied(self, celery, session):
        """If an equal number of cells have region=None, the area is None."""

        # Bornholm, an island in the Baltic sea, not identified as part of Denmark
        cell = self.cell_factory(
            radio=Radio.wcdma,
            mcc=204,
            mnc=175,
            lac=1515,
            cid=13241603,
            lat=55.115,
            lon=14.88,
            radius=10,
            region=None,
        )
        assert cell.region is None

        # Reeuwijk, Netherlands
        self.cell_factory(
            radio=Radio.wcdma,
            mcc=cell.mcc,
            mnc=cell.mnc,
            lac=cell.lac,
            cid=cell.cid + 2,
            lat=52.056,
            lon=4.733,
            radius=10,
            region="NL",
        )
        session.flush()

        self.area_queue(celery).enqueue([area_id(cell)])
        self.task.delay().get()

        area = session.query(self.area_model).one()
        assert area.region is None
