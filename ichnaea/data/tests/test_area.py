from ichnaea.data.tasks import (
    location_update_cell,
    remove_cell,
    scan_areas,
)
from ichnaea.models import (
    Cell,
    CellArea,
    CellObservation,
    Radio,
)
from ichnaea.tests.base import CeleryTestCase
from ichnaea.tests.factories import (
    CellAreaFactory,
)
from ichnaea import util


class TestArea(CeleryTestCase):

    def add_line_of_cells_and_scan_lac(self):
        session = self.session
        big = 1.0
        small = big / 10
        keys = dict(radio=Radio.cdma, mcc=1, mnc=1, lac=1)
        observations = [
            CellObservation(lat=ctr + xd, lon=ctr + yd, cid=cell, **keys)
            for cell in range(10)
            for ctr in [cell * big]
            for (xd, yd) in [(small, small),
                             (small, -small),
                             (-small, small),
                             (-small, -small)]
        ]
        session.add_all(observations)

        cells = [
            Cell(lat=ctr, lon=ctr, cid=cell,
                 new_measures=4, total_measures=1, **keys)
            for cell in range(10)
            for ctr in [cell * big]
        ]

        session.add_all(cells)
        session.commit()
        result = location_update_cell.delay(min_new=0,
                                            max_new=9999,
                                            batch=len(observations))
        self.assertEqual(result.get(), (len(cells), 0))
        scan_areas.delay()

    def test_removal_updates_lac(self):
        session = self.session
        keys = dict(radio=Radio.cdma, mcc=1, mnc=1, lac=1)

        # setup: build LAC as above
        self.add_line_of_cells_and_scan_lac()

        # confirm we got one
        lac = session.query(CellArea).filter(CellArea.lac == 1).first()

        self.assertEqual(lac.lat, 4.5)
        self.assertEqual(lac.lon, 4.5)
        self.assertEqual(lac.range, 723001)

        # Remove cells one by one checking that the LAC
        # changes shape along the way.
        steps = [
            ((5.0, 5.0), 644242),
            ((5.5, 5.5), 565475),
            ((6.0, 6.0), 486721),
            ((6.5, 6.5), 408000),
            ((7.0, 7.0), 329334),
            ((7.5, 7.5), 250743),
            ((8.0, 8.0), 172249),
            ((8.5, 8.5), 93871),
            ((9.0, 9.0), 15630),
        ]
        for i in range(9):
            session.expire(lac)
            k = Cell.to_hashkey(cid=i, **keys)
            result = remove_cell.delay([k])
            self.assertEqual(1, result.get())
            result = scan_areas.delay()
            self.assertEqual(1, result.get())
            lac = session.query(CellArea).filter(CellArea.lac == 1).first()

            self.assertEqual(lac.lat, steps[i][0][0])
            self.assertEqual(lac.lon, steps[i][0][1])
            self.assertEqual(lac.range, steps[i][1])

        # Remove final cell, check LAC is gone
        k = Cell.to_hashkey(cid=9, **keys)
        result = remove_cell.delay([k])
        self.assertEqual(1, result.get())
        result = scan_areas.delay()
        self.assertEqual(1, result.get())
        lac = session.query(CellArea).filter(CellArea.lac == 1).first()
        self.assertEqual(lac, None)

    def test_scan_areas_asymmetric(self):
        session = self.session
        big = 0.1
        small = big / 10
        keys = dict(radio=Radio.cdma, mcc=1, mnc=1, lac=1)
        observations = [
            CellObservation(lat=ctr + xd, lon=ctr + yd, cid=cell, **keys)
            for cell in range(6)
            for ctr in [(2 ** cell) * big]
            for (xd, yd) in [(small, small),
                             (small, -small),
                             (-small, small),
                             (-small, -small)]
        ]
        session.add_all(observations)

        cells = [
            Cell(lat=ctr, lon=ctr, cid=cell,
                 new_measures=4, total_measures=1, **keys)
            for cell in range(6)
            for ctr in [(2 ** cell) * big]
        ]

        session.add_all(cells)
        session.commit()
        result = location_update_cell.delay(min_new=0,
                                            max_new=9999,
                                            batch=len(observations))
        self.assertEqual(result.get(), (len(cells), 0))
        scan_areas.delay()
        lac = session.query(CellArea).filter(CellArea.lac == 1).first()

        # We produced a sequence of 0.02-degree-on-a-side
        # cell bounding boxes centered at
        # [0, 0.2, 0.4, 0.8, 1.6, 3.2] degrees.
        # So the lower-left corner is at (-0.01, -0.01)
        # and the upper-right corner is at (3.21, 3.21)
        # we should therefore see a LAC centroid at (1.05, 1.05)
        # with a range of 339.540m
        self.assertEqual(lac.lat, 1.05)
        self.assertEqual(lac.lon, 1.05)
        self.assertEqual(lac.range, 339540)

    def test_scan_areas_race_with_location_update(self):
        session = self.session

        # First batch of cell observations for CID 1
        keys = dict(radio=Radio.cdma, mcc=1, mnc=1, lac=1, cid=1)
        cell = Cell(new_measures=4, total_measures=1, **keys)
        observations = [
            CellObservation(lat=1.0, lon=1.0, **keys),
            CellObservation(lat=1.0, lon=1.0, **keys),
            CellObservation(lat=1.0, lon=1.0, **keys),
            CellObservation(lat=1.0, lon=1.0, **keys),
        ]
        session.add(cell)
        session.add_all(observations)
        session.commit()

        # Periodic location_update_cell runs and updates CID 1
        # to have a location, inserts LAC 1 with new_measures=1
        # which will be picked up by the next scan_lac.
        result = location_update_cell.delay(min_new=1)
        self.assertEqual(result.get(), (1, 0))

        # Second batch of cell observations for CID 2
        keys['cid'] = 2
        cell = Cell(new_measures=4, total_measures=1, **keys)
        observations = [
            CellObservation(lat=1.0, lon=1.0, **keys),
            CellObservation(lat=1.0, lon=1.0, **keys),
            CellObservation(lat=1.0, lon=1.0, **keys),
            CellObservation(lat=1.0, lon=1.0, **keys),
        ]
        session.add(cell)
        session.add_all(observations)
        session.commit()

        # Periodic LAC scan runs, picking up LAC 1; this could
        # accidentally pick up CID 2, but it should not since it
        # has not had its location updated yet. If there's no
        # exception here, CID 2 is properly ignored.
        scan_areas.delay()

    def test_scan_areas_empty(self):
        # test tasks with an empty queue
        self.assertEqual(scan_areas.delay().get(), 0)
        self.check_raven(total=0)

    def test_scan_areas_remove(self):
        # create an orphaned lac entry
        area = CellAreaFactory()
        self.session.flush()
        data_queue = self.celery_app.data_queues['update_cellarea']
        data_queue.enqueue([area.hashkey()])

        # after scanning the orphaned record gets removed
        self.assertEqual(scan_areas.delay().get(), 1)
        areas = self.session.query(CellArea).all()
        self.assertEqual(areas, [])

    def test_scan_areas_update(self):
        session = self.session
        self.add_line_of_cells_and_scan_lac()
        today = util.utcnow().date()

        lac = session.query(CellArea).filter(Cell.lac == 1).first()

        # We produced a sequence of 0.2-degree-on-a-side
        # cell bounding boxes centered at [0, 1, 2, ..., 9]
        # degrees. So the lower-left corner is at (-0.1, -0.1)
        # and the upper-right corner is at (9.1, 9.1)
        # we should therefore see a LAC centroid at (4.5, 4.5)
        # with a range of 723,001m
        self.assertEqual(lac.lat, 4.5)
        self.assertEqual(lac.lon, 4.5)
        self.assertEqual(lac.range, 723001)
        self.assertEqual(lac.created.date(), today)
        self.assertEqual(lac.modified.date(), today)
        self.assertEqual(lac.num_cells, 10)
