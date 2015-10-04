from ichnaea.data.tasks import (
    update_cellarea,
    update_cellarea_ocid,
)
from ichnaea.models import (
    encode_cellarea,
    CellArea,
    CellAreaOCID,
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
        self.assertEqual(area.radius, 0)
        self.assertEqual(area.num_cells, 1)
        self.assertEqual(area.avg_cell_radius, cell.radius)

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
        self.assertEqual(area.radius, 0)
        self.assertEqual(area.num_cells, 1)
        self.assertEqual(area.avg_cell_radius, 200)

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
