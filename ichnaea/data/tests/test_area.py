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
    CellFactory,
    CellOCIDFactory,
)


class TestArea(CeleryTestCase):

    def setUp(self):
        super(TestArea, self).setUp()
        self.area_queue = self.celery_app.data_queues['update_cellarea']
        self.obs_queue = self.celery_app.data_queues['update_cell']

    def test_empty(self):
        update_cellarea.delay().get()

    def test_new(self):
        cell = CellFactory()
        self.session.flush()

        areaid = encode_cellarea(
            cell.radio, cell.mcc, cell.mnc, cell.lac)
        self.area_queue.enqueue([areaid], json=False)
        update_cellarea.delay().get()

        area = self.session.query(CellArea).one()
        self.assertAlmostEqual(area.lat, cell.lat)
        self.assertAlmostEqual(area.lon, cell.lon)
        self.assertEqual(area.range, 0)  # BBB
        self.assertEqual(area.num_cells, 1)
        self.assertEqual(area.avg_cell_range, cell.range)  # BBB

    def test_remove(self):
        area = CellAreaFactory()
        self.session.flush()

        areaid = encode_cellarea(*area.areaid)
        self.area_queue.enqueue([areaid], json=False)
        update_cellarea.delay().get()
        self.assertEqual(self.session.query(CellArea).count(), 0)

    def test_update(self):
        area = CellAreaFactory(num_cells=2, range=500, avg_cell_range=100)
        cell = CellFactory(
            lat=area.lat, lon=area.lon, range=200,
            radio=area.radio, mcc=area.mcc, mnc=area.mnc, lac=area.lac)
        self.session.commit()

        areaid = encode_cellarea(*area.areaid)
        self.area_queue.enqueue([areaid], json=False)
        update_cellarea.delay().get()

        self.session.refresh(area)
        self.assertAlmostEqual(area.lat, cell.lat)
        self.assertAlmostEqual(area.lon, cell.lon)
        self.assertEqual(area.range, 0)  # BBB
        self.assertEqual(area.num_cells, 1)
        self.assertEqual(area.avg_cell_range, 200)  # BBB

    def test_update_incomplete_cell(self):
        area = CellAreaFactory(range=500)
        area_key = {'radio': area.radio, 'mcc': area.mcc,
                    'mnc': area.mnc, 'lac': area.lac}
        cell = CellFactory(lat=area.lat + 0.0002, lon=area.lon, **area_key)
        CellFactory(lat=None, lon=None, **area_key)
        CellFactory(lat=area.lat, lon=area.lon,
                    max_lat=None, min_lon=None, **area_key)
        self.session.commit()

        areaid = encode_cellarea(*area.areaid)
        self.area_queue.enqueue([areaid], json=False)
        update_cellarea.delay().get()

        self.session.refresh(area)
        self.assertAlmostEqual(area.lat, cell.lat - 0.0001)
        self.assertAlmostEqual(area.lon, cell.lon)
        self.assertEqual(area.num_cells, 2)


class TestAreaOCID(CeleryTestCase):

    def setUp(self):
        super(TestAreaOCID, self).setUp()
        self.area_queue = self.celery_app.data_queues['update_cellarea_ocid']

    def test_new(self):
        cell = CellOCIDFactory()
        self.session.flush()

        areaid = encode_cellarea(
            cell.radio, cell.mcc, cell.mnc, cell.lac)
        self.area_queue.enqueue([areaid], json=False)
        update_cellarea_ocid.delay().get()

        area = self.session.query(CellAreaOCID).one()
        self.assertAlmostEqual(area.lat, cell.lat)
        self.assertAlmostEqual(area.lon, cell.lon)
        self.assertEqual(area.country, 'GB')
        self.assertEqual(area.radius, 0)
        self.assertEqual(area.num_cells, 1)
        self.assertEqual(area.avg_cell_radius, cell.radius)

    def test_remove(self):
        area = CellAreaOCIDFactory()
        self.session.flush()

        areaid = encode_cellarea(*area.areaid)
        self.area_queue.enqueue([areaid], json=False)
        update_cellarea_ocid.delay().get()
        self.assertEqual(self.session.query(CellAreaOCID).count(), 0)

    def test_region_area(self):
        cell = CellOCIDFactory(
            radio=Radio.gsm, mcc=425, mnc=1, lac=1, cid=1,
            lat=32.2, lon=35.0, country='XW', radius=10000)
        CellOCIDFactory(
            radio=cell.radio, mcc=cell.mcc, mnc=cell.mnc, lac=cell.lac, cid=2,
            lat=32.2, lon=34.9, country='IL', radius=10000)
        self.session.flush()

        self.area_queue.enqueue([cell.areaid], json=False)
        update_cellarea_ocid.delay().get()

        area = self.session.query(CellAreaOCID).one()
        self.assertEqual(area.country, 'IL')

    def test_region_area_outside(self):
        cell = CellOCIDFactory(
            radio=Radio.gsm, mcc=310, mnc=1, lac=1, cid=1,
            lat=18.33, lon=-64.9, country='PR', radius=10000)
        CellOCIDFactory(
            radio=cell.radio, mcc=cell.mcc, mnc=cell.mnc, lac=cell.lac, cid=2,
            lat=18.34, lon=-64.9, country='PR', radius=10000)
        CellOCIDFactory(
            radio=cell.radio, mcc=cell.mcc, mnc=cell.mnc, lac=cell.lac, cid=3,
            lat=35.8, lon=-83.1, country='US', radius=10000)
        self.session.flush()

        self.area_queue.enqueue([cell.areaid], json=False)
        update_cellarea_ocid.delay().get()

        area = self.session.query(CellAreaOCID).one()
        self.assertEqual(area.country, 'PR')

    def test_region_area_outside_tie(self):
        cell = CellOCIDFactory(
            radio=Radio.gsm, mcc=310, mnc=1, lac=1, cid=1,
            lat=18.33, lon=-64.9, country='PR', radius=10000)
        CellOCIDFactory(
            radio=cell.radio, mcc=cell.mcc, mnc=cell.mnc, lac=cell.lac, cid=2,
            lat=18.34, lon=-64.9, country='PR', radius=10000)
        self.session.flush()

        self.area_queue.enqueue([cell.areaid], json=False)
        update_cellarea_ocid.delay().get()

        area = self.session.query(CellAreaOCID).one()
        self.assertEqual(area.country, 'PR')
