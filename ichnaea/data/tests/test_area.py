from datetime import timedelta

from ichnaea.data.tasks import (
    update_cellarea,
    update_cellarea_ocid,
)
from ichnaea.models import (
    encode_cellarea,
    CellArea,
    CellAreaOCID,
    Radio,
)
from ichnaea.tests.base import CeleryTestCase
from ichnaea.tests.factories import (
    CellAreaFactory,
    CellAreaOCIDFactory,
    CellShardFactory,
    CellShardOCIDFactory,
)
from ichnaea import util


class BaseTest(object):

    area_model = None
    area_factory = None
    cell_factory = None
    task = None

    def test_empty(self):
        self.task.delay().get()

    def test_new(self):
        cell = self.cell_factory()
        self.session.flush()

        areaid = encode_cellarea(
            cell.radio, cell.mcc, cell.mnc, cell.lac)
        self.area_queue.enqueue([areaid])
        self.task.delay().get()

        area = self.session.query(self.area_model).one()
        self.assertAlmostEqual(area.lat, cell.lat)
        self.assertAlmostEqual(area.lon, cell.lon)
        self.assertEqual(area.radius, 0)
        self.assertEqual(area.region, 'GB')
        self.assertEqual(area.avg_cell_radius, cell.radius)
        self.assertEqual(area.num_cells, 1)
        self.assertEqual(area.last_seen, cell.last_seen)

    def test_remove(self):
        area = self.area_factory()
        self.session.flush()

        areaid = encode_cellarea(*area.areaid)
        self.area_queue.enqueue([areaid])
        self.task.delay().get()
        self.assertEqual(self.session.query(self.area_model).count(), 0)

    def test_update(self):
        today = util.utcnow().date()
        yesterday = today - timedelta(days=1)
        area = self.area_factory(
            num_cells=2, radius=500, avg_cell_radius=100, last_seen=yesterday)
        cell = self.cell_factory(
            lat=area.lat, lon=area.lon, radius=200, last_seen=today,
            radio=area.radio, mcc=area.mcc, mnc=area.mnc, lac=area.lac)
        self.cell_factory(
            lat=area.lat, lon=area.lon, radius=300, last_seen=yesterday,
            radio=area.radio, mcc=area.mcc, mnc=area.mnc, lac=area.lac)
        self.session.commit()

        areaid = encode_cellarea(*area.areaid)
        self.area_queue.enqueue([areaid])
        self.task.delay().get()

        self.session.refresh(area)
        self.assertAlmostEqual(area.lat, cell.lat)
        self.assertAlmostEqual(area.lon, cell.lon)
        self.assertEqual(area.radius, 0)
        self.assertEqual(area.region, 'GB')
        self.assertEqual(area.avg_cell_radius, 250)
        self.assertEqual(area.num_cells, 2)
        self.assertEqual(area.last_seen, today)

    def test_update_incomplete_cell(self):
        area = self.area_factory(radius=500)
        area_key = {'radio': area.radio, 'mcc': area.mcc,
                    'mnc': area.mnc, 'lac': area.lac}
        cell = self.cell_factory(lat=area.lat + 0.0002,
                                 lon=area.lon, **area_key)
        self.cell_factory(lat=None, lon=None, **area_key)
        self.cell_factory(lat=area.lat, lon=area.lon,
                          max_lat=None, min_lon=None, **area_key)
        self.session.commit()

        areaid = encode_cellarea(*area.areaid)
        self.area_queue.enqueue([areaid])
        self.task.delay().get()

        self.session.refresh(area)
        self.assertAlmostEqual(area.lat, cell.lat - 0.0001)
        self.assertAlmostEqual(area.lon, cell.lon)
        self.assertEqual(area.num_cells, 2)

    def test_region(self):
        cell = self.cell_factory(
            radio=Radio.gsm, mcc=425, mnc=1, lac=1, cid=1,
            lat=32.2, lon=35.0, radius=10000, region='XW')
        self.cell_factory(
            radio=cell.radio, mcc=cell.mcc, mnc=cell.mnc, lac=cell.lac, cid=2,
            lat=32.2, lon=34.9, radius=10000, region='IL')
        self.session.flush()

        self.area_queue.enqueue([cell.areaid])
        self.task.delay().get()

        area = self.session.query(self.area_model).one()
        self.assertEqual(area.region, 'IL')

    def test_region_outside(self):
        cell = self.cell_factory(
            radio=Radio.gsm, mcc=310, mnc=1, lac=1, cid=1,
            lat=18.33, lon=-64.9, radius=10000, region='PR')
        self.cell_factory(
            radio=cell.radio, mcc=cell.mcc, mnc=cell.mnc, lac=cell.lac, cid=2,
            lat=18.34, lon=-64.9, radius=10000, region='PR')
        self.cell_factory(
            radio=cell.radio, mcc=cell.mcc, mnc=cell.mnc, lac=cell.lac, cid=3,
            lat=35.8, lon=-83.1, radius=10000, region='US')
        self.session.flush()

        self.area_queue.enqueue([cell.areaid])
        self.task.delay().get()

        area = self.session.query(self.area_model).one()
        self.assertEqual(area.region, 'PR')

    def test_region_outside_tie(self):
        cell = self.cell_factory(
            radio=Radio.gsm, mcc=310, mnc=1, lac=1, cid=1,
            lat=18.33, lon=-64.9, radius=10000, region='PR')
        self.cell_factory(
            radio=cell.radio, mcc=cell.mcc, mnc=cell.mnc, lac=cell.lac, cid=2,
            lat=18.34, lon=-64.9, radius=10000, region='PR')
        self.session.flush()

        self.area_queue.enqueue([cell.areaid])
        self.task.delay().get()

        area = self.session.query(self.area_model).one()
        self.assertEqual(area.region, 'PR')


class TestArea(BaseTest, CeleryTestCase):

    area_model = CellArea
    area_factory = CellAreaFactory
    cell_factory = CellShardFactory
    task = update_cellarea

    def setUp(self):
        super(TestArea, self).setUp()
        self.area_queue = self.celery_app.data_queues['update_cellarea']


class TestAreaOCID(BaseTest, CeleryTestCase):

    area_model = CellAreaOCID
    area_factory = CellAreaOCIDFactory
    cell_factory = CellShardOCIDFactory
    task = update_cellarea_ocid

    def setUp(self):
        super(TestAreaOCID, self).setUp()
        self.area_queue = self.celery_app.data_queues['update_cellarea_ocid']
