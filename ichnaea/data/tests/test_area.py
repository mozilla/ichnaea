from ichnaea.data.tasks import scan_areas
from ichnaea.models import CellArea
from ichnaea.tests.base import CeleryTestCase
from ichnaea.tests.factories import (
    CellAreaFactory,
    CellFactory,
)


class TestArea(CeleryTestCase):

    def setUp(self):
        super(TestArea, self).setUp()
        self.area_queue = self.celery_app.data_queues['update_cellarea']
        self.obs_queue = self.celery_app.data_queues['update_cell']

    def test_empty(self):
        # test tasks with an empty queue
        self.assertEqual(scan_areas.delay().get(), 0)

    def test_new(self):
        cell = CellFactory()
        self.session.flush()

        area_key = CellArea.to_hashkey(cell)
        self.area_queue.enqueue([area_key])
        self.assertEqual(scan_areas.delay().get(), 1)

        area = self.session.query(CellArea).one()
        self.assertAlmostEqual(area.lat, cell.lat)
        self.assertAlmostEqual(area.lon, cell.lon)
        self.assertEqual(area.range, 0)
        self.assertEqual(area.num_cells, 1)
        self.assertEqual(area.avg_cell_range, cell.range)

    def test_remove(self):
        area = CellAreaFactory()
        self.session.flush()

        self.area_queue.enqueue([area.hashkey()])
        self.assertEqual(scan_areas.delay().get(), 1)
        self.assertEqual(self.session.query(CellArea).count(), 0)

    def test_update(self):
        area = CellAreaFactory(num_cells=2, range=500, avg_cell_range=100)
        area_key = area.hashkey()
        cell = CellFactory(
            lat=area.lat, lon=area.lon, range=200, **area_key.__dict__)
        self.session.flush()

        self.area_queue.enqueue([area_key])
        self.assertEqual(scan_areas.delay().get(), 1)
        self.session.refresh(area)

        area = self.session.query(CellArea).one()
        self.assertAlmostEqual(area.lat, cell.lat)
        self.assertAlmostEqual(area.lon, cell.lon)
        self.assertEqual(area.range, 0)
        self.assertEqual(area.num_cells, 1)
        self.assertEqual(area.avg_cell_range, 200)

    def test_update_incomplete_cell(self):
        area = CellAreaFactory(range=500)
        area_key = area.hashkey()
        cell = CellFactory(
            lat=area.lat + 0.0002, lon=area.lon, **area_key.__dict__)
        CellFactory(lat=None, lon=None, **area_key.__dict__)
        CellFactory(lat=area.lat, lon=area.lon,
                    max_lat=None, min_lon=None, **area_key.__dict__)
        self.session.flush()

        self.area_queue.enqueue([area_key])
        self.assertEqual(scan_areas.delay().get(), 1)
        self.session.refresh(area)

        area = self.session.query(CellArea).one()
        self.assertAlmostEqual(area.lat, cell.lat - 0.0001)
        self.assertAlmostEqual(area.lon, cell.lon)
        self.assertEqual(area.num_cells, 2)
