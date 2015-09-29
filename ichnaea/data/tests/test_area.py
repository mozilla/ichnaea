from ichnaea.data.tasks import scan_areas
from ichnaea.models import (
    encode_cellarea,
    CellArea,
)
from ichnaea.tests.base import CeleryTestCase
from ichnaea.tests.factories import (
    CellAreaFactory,
    CellFactory,
)


class TestArea(CeleryTestCase):

    def setUp(self):
        super(TestArea, self).setUp()
        self.area_queue = self.celery_app.data_queues['update_cell_lac']
        self.obs_queue = self.celery_app.data_queues['update_cell']

    def test_empty(self):
        # test tasks with an empty queue
        self.assertEqual(scan_areas.delay().get(), 0)

    def test_new(self):
        cell = CellFactory()
        self.session.flush()

        areaid = encode_cellarea(
            cell.radio, cell.mcc, cell.mnc, cell.lac, codec='base64')
        self.area_queue.enqueue([areaid])
        self.assertEqual(scan_areas.delay().get(), 1)

        area = self.session.query(CellArea).one()
        self.assertAlmostEqual(area.lat, cell.lat)
        self.assertAlmostEqual(area.lon, cell.lon)
        self.assertEqual(area.radius, 0)
        self.assertEqual(area.num_cells, 1)
        self.assertEqual(area.avg_cell_radius, cell.radius)

    def test_remove(self):
        area = CellAreaFactory()
        self.session.flush()

        areaid = encode_cellarea(*area.areaid, codec='base64')
        self.area_queue.enqueue([areaid])
        self.assertEqual(scan_areas.delay().get(), 1)
        self.assertEqual(self.session.query(CellArea).count(), 0)

    def test_update(self):
        area = CellAreaFactory(num_cells=2, range=500, avg_cell_range=100)
        cell = CellFactory(
            lat=area.lat, lon=area.lon, range=200,
            radio=area.radio, mcc=area.mcc, mnc=area.mnc, lac=area.lac)
        self.session.commit()

        areaid = encode_cellarea(*area.areaid, codec='base64')
        self.area_queue.enqueue([areaid])
        self.assertEqual(scan_areas.delay().get(), 1)

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

        areaid = encode_cellarea(*area.areaid, codec='base64')
        self.area_queue.enqueue([areaid])
        self.assertEqual(scan_areas.delay().get(), 1)

        self.session.refresh(area)
        self.assertAlmostEqual(area.lat, cell.lat - 0.0001)
        self.assertAlmostEqual(area.lon, cell.lon)
        self.assertEqual(area.num_cells, 2)
