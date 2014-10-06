from datetime import timedelta

from ichnaea.data.tasks import (
    location_update_cell,
    location_update_cell_backfill,
    location_update_wifi,
    remove_cell,
    remove_wifi,
    scan_lacs,
)
from ichnaea.models import (
    Cell,
    CellBlacklist,
    CellKey,
    CellMeasure,
    Wifi,
    WifiBlacklist,
    WifiMeasure,
    to_cellkey,
    CELLID_LAC,
)
from ichnaea.tests.base import CeleryTestCase
from ichnaea import util


class TestCell(CeleryTestCase):

    def add_line_of_cells_and_scan_lac(self):
        session = self.db_master_session
        big = 1.0
        small = big / 10
        keys = dict(radio=1, mcc=1, mnc=1, lac=1)
        measures = [
            CellMeasure(lat=ctr + xd, lon=ctr + yd, cid=cell, **keys)
            for cell in range(10)
            for ctr in [cell * big]
            for (xd, yd) in [(small, small),
                             (small, -small),
                             (-small, small),
                             (-small, -small)]
        ]
        session.add_all(measures)

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
                                            batch=len(measures))
        self.assertEqual(result.get(), (len(cells), 0))
        scan_lacs.delay()

    def test_blacklist_moving_cells(self):
        now = util.utcnow()
        long_ago = now - timedelta(days=40)
        session = self.db_master_session

        k1 = dict(radio=1, mcc=1, mnc=2, lac=3, cid=4)
        k2 = dict(radio=1, mcc=1, mnc=2, lac=6, cid=8)
        k3 = dict(radio=1, mcc=1, mnc=2, lac=9, cid=12)
        k4 = dict(radio=1, mcc=1, mnc=2, lac=12, cid=16)
        k5 = dict(radio=1, mcc=1, mnc=2, lac=15, cid=20)
        k6 = dict(radio=1, mcc=1, mnc=2, lac=18, cid=24)

        keys = set([CellKey(**k) for k in [k1, k2, k3, k4, k5, k6]])

        # keys k2, k3 and k4 are expected to be detected as moving
        data = [
            # a cell with an entry but no prior position
            Cell(new_measures=3, total_measures=0, **k1),
            CellMeasure(lat=1.001, lon=1.001, **k1),
            CellMeasure(lat=1.002, lon=1.005, **k1),
            CellMeasure(lat=1.003, lon=1.009, **k1),
            # a cell with a prior known position
            Cell(lat=2.0, lon=2.0,
                 new_measures=2, total_measures=1, **k2),
            CellMeasure(lat=2.0, lon=2.0, **k2),
            CellMeasure(lat=4.0, lon=2.0, **k2),
            # a cell with a very different prior position
            Cell(lat=1.0, lon=1.0,
                 new_measures=2, total_measures=1, **k3),
            CellMeasure(lat=3.0, lon=3.0, **k3),
            CellMeasure(lat=-3.0, lon=3.0, **k3),
            # another cell with a prior known position (and negative lat)
            Cell(lat=-4.0, lon=4.0,
                 new_measures=2, total_measures=1, **k4),
            CellMeasure(lat=-4.0, lon=4.0, **k4),
            CellMeasure(lat=-6.0, lon=4.0, **k4),
            # an already blacklisted cell
            CellBlacklist(**k5),
            CellMeasure(lat=5.0, lon=5.0, **k5),
            CellMeasure(lat=8.0, lon=5.0, **k5),
            # a cell with an old different record we ignore, position
            # estimate has been updated since
            Cell(lat=6.0, lon=6.0,
                 new_measures=2, total_measures=1, **k6),
            CellMeasure(lat=6.9, lon=6.9, time=long_ago, **k6),
            CellMeasure(lat=6.0, lon=6.0, **k6),
            CellMeasure(lat=6.001, lon=6, **k6),
        ]
        session.add_all(data)
        session.commit()

        result = location_update_cell.delay(min_new=1)
        self.assertEqual(result.get(), (5, 3))

        black = session.query(CellBlacklist).all()
        self.assertEqual(set([to_cellkey(b) for b in black]),
                         set([CellKey(**k) for k in [k2, k3, k4, k5]]))

        measures = session.query(CellMeasure).all()
        self.assertEqual(len(measures), 14)
        self.assertEqual(set([to_cellkey(m) for m in measures]), keys)

        # test duplicate call
        result = location_update_cell.delay(min_new=1)
        self.assertEqual(result.get(), 0)

        self.check_stats(
            total=6,
            timer=[
                # We made duplicate calls
                ('task.data.location_update_cell', 2),
                # One of those would've scheduled a remove_cell task
                ('task.data.remove_cell', 1)
            ],
            gauge=[
                ('task.data.location_update_cell.new_measures_1_100', 2),
            ])

    def test_location_update_cell(self):
        now = util.utcnow()
        before = now - timedelta(days=1)
        session = self.db_master_session
        k1 = dict(radio=1, mcc=1, mnc=2, lac=3, cid=4)
        k2 = dict(radio=1, mcc=1, mnc=2, lac=6, cid=8)
        k3 = dict(radio=1, mcc=1, mnc=2, lac=-1, cid=-1)
        data = [
            Cell(new_measures=3, total_measures=5, **k1),
            CellMeasure(lat=1.0, lon=1.0, **k1),
            CellMeasure(lat=1.002, lon=1.003, **k1),
            CellMeasure(lat=1.004, lon=1.006, **k1),
            # The lac, cid are invalid and should be skipped
            CellMeasure(lat=1.5, lon=1.5, **k3),
            CellMeasure(lat=1.502, lon=1.503, **k3),

            Cell(lat=2.0, lon=2.0,
                 new_measures=2, total_measures=4, **k2),
            # the lat/lon is bogus and mismatches the line above on purpose
            # to make sure old measures are skipped
            CellMeasure(lat=-1.0, lon=-1.0, created=before, **k2),
            CellMeasure(lat=-1.0, lon=-1.0, created=before, **k2),
            CellMeasure(lat=2.002, lon=2.004, **k2),
            CellMeasure(lat=2.002, lon=2.004, **k2),

        ]
        session.add_all(data)
        session.commit()

        result = location_update_cell.delay(min_new=1)
        self.assertEqual(result.get(), (2, 0))
        self.check_stats(
            total=2,
            timer=['task.data.location_update_cell'],
            gauge=['task.data.location_update_cell.new_measures_1_100'],
        )

        cells = session.query(Cell).filter(Cell.cid != CELLID_LAC).all()
        self.assertEqual(len(cells), 2)
        self.assertEqual([c.new_measures for c in cells], [0, 0])
        for cell in cells:
            if cell.cid == 4:
                self.assertEqual(cell.lat, 1.002)
                self.assertEqual(cell.lon, 1.003)
            elif cell.cid == 8:
                self.assertEqual(cell.lat, 2.001)
                self.assertEqual(cell.lon, 2.002)

    def test_location_update_cell_backfill(self):
        session = self.db_master_session
        k1 = dict(radio=1, mcc=1, mnc=2, lac=3, cid=4)
        data = [
            Cell(lat=1.001, lon=1.001, new_measures=0,
                 total_measures=1, **k1),
            CellMeasure(lat=1.0, lon=1.0, **k1),
            CellMeasure(lat=1.005, lon=1.008, **k1),
        ]
        session.add_all(data)
        session.commit()

        query = session.query(CellMeasure.id)
        cm_ids = [x[0] for x in query.all()]

        # TODO: refactor this to be constants in the method
        new_measures = [((1, 1, 2, 3, 4), cm_ids)]

        result = location_update_cell_backfill.delay(new_measures)
        self.assertEqual(result.get(), (1, 0))

        cells = session.query(Cell).filter(Cell.cid != CELLID_LAC).all()
        self.assertEqual(len(cells), 1)
        cell = cells[0]
        self.assertEqual(cell.lat, 1.002)
        self.assertEqual(cell.lon, 1.003)
        self.assertEqual(cell.new_measures, 0)
        self.assertEqual(cell.total_measures, 3)

    def test_max_min_range_update(self):
        session = self.db_master_session

        k1 = dict(radio=1, mcc=1, mnc=2, lac=3, cid=4)
        data = [
            Cell(lat=1.001, lon=-1.001,
                 max_lat=1.002, min_lat=1.0,
                 max_lon=-1.0, min_lon=-1.002,
                 new_measures=2, total_measures=4, **k1),
            CellMeasure(lat=1.001, lon=-1.003, **k1),
            CellMeasure(lat=1.005, lon=-1.007, **k1),
        ]
        session.add_all(data)
        session.commit()

        result = location_update_cell.delay(min_new=1)
        self.assertEqual(result.get(), (1, 0))

        cells = session.query(Cell).filter(Cell.cid != CELLID_LAC).all()
        self.assertEqual(len(cells), 1)
        cell = cells[0]
        self.assertEqual(cell.lat, 1.002)
        self.assertEqual(cell.max_lat, 1.005)
        self.assertEqual(cell.min_lat, 1.0)
        self.assertEqual(cell.lon, -1.003)
        self.assertEqual(cell.max_lon, -1.0)
        self.assertEqual(cell.min_lon, -1.007)

        # independent calculation: the cell bounding box is
        # (1.000, -1.007) to (1.005, -1.000), with centroid
        # at (1.002, -1.003); worst distance from centroid
        # to any corner is 556m
        self.assertEqual(cell.range, 556)

    def test_removal_updates_lac(self):
        session = self.db_master_session
        keys = dict(radio=1, mcc=1, mnc=1, lac=1)

        # setup: build LAC as above
        self.add_line_of_cells_and_scan_lac()

        # confirm we got one
        lac = session.query(Cell).filter(
            Cell.lac == 1,
            Cell.cid == CELLID_LAC).first()

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
            k = CellKey(cid=i, **keys)
            result = remove_cell.delay([k])
            self.assertEqual(1, result.get())
            result = scan_lacs.delay()
            self.assertEqual(1, result.get())
            lac = session.query(Cell).filter(
                Cell.lac == 1,
                Cell.cid == CELLID_LAC).first()

            self.assertEqual(lac.lat, steps[i][0][0])
            self.assertEqual(lac.lon, steps[i][0][1])
            self.assertEqual(lac.range, steps[i][1])

        # Remove final cell, check LAC is gone
        k = CellKey(cid=9, **keys)
        result = remove_cell.delay([k])
        self.assertEqual(1, result.get())
        result = scan_lacs.delay()
        self.assertEqual(0, result.get())
        lac = session.query(Cell).filter(
            Cell.lac == 1,
            Cell.cid == CELLID_LAC).first()
        self.assertEqual(lac, None)

    def test_scan_lacs_asymmetric(self):
        session = self.db_master_session
        big = 0.1
        small = big / 10
        keys = dict(radio=1, mcc=1, mnc=1, lac=1)
        measures = [
            CellMeasure(lat=ctr + xd, lon=ctr + yd, cid=cell, **keys)
            for cell in range(6)
            for ctr in [(2 ** cell) * big]
            for (xd, yd) in [(small, small),
                             (small, -small),
                             (-small, small),
                             (-small, -small)]
        ]
        session.add_all(measures)

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
                                            batch=len(measures))
        self.assertEqual(result.get(), (len(cells), 0))
        scan_lacs.delay()
        lac = session.query(Cell).filter(
            Cell.lac == 1,
            Cell.cid == CELLID_LAC).first()

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

    def test_scan_lacs_race_with_location_update(self):
        session = self.db_master_session

        # First batch of cell measurements for CID 1
        keys = dict(radio=1, mcc=1, mnc=1, lac=1, cid=1)
        cell = Cell(new_measures=4, total_measures=1, **keys)
        measures = [
            CellMeasure(lat=1.0, lon=1.0, **keys),
            CellMeasure(lat=1.0, lon=1.0, **keys),
            CellMeasure(lat=1.0, lon=1.0, **keys),
            CellMeasure(lat=1.0, lon=1.0, **keys),
        ]
        session.add(cell)
        session.add_all(measures)
        session.commit()

        # Periodic location_update_cell runs and updates CID 1
        # to have a location, inserts LAC 1 with new_measures=1
        # which will be picked up by the next scan_lac.
        result = location_update_cell.delay(min_new=1)
        self.assertEqual(result.get(), (1, 0))

        # Second batch of cell measurements for CID 2
        keys['cid'] = 2
        cell = Cell(new_measures=4, total_measures=1, **keys)
        measures = [
            CellMeasure(lat=1.0, lon=1.0, **keys),
            CellMeasure(lat=1.0, lon=1.0, **keys),
            CellMeasure(lat=1.0, lon=1.0, **keys),
            CellMeasure(lat=1.0, lon=1.0, **keys),
        ]
        session.add(cell)
        session.add_all(measures)
        session.commit()

        # Periodic LAC scan runs, picking up LAC 1; this could
        # accidentally pick up CID 2, but it should not since it
        # has not had its location updated yet. If there's no
        # exception here, CID 2 is properly ignored.
        scan_lacs.delay()

    def test_scan_lacs_update(self):
        session = self.db_master_session
        self.add_line_of_cells_and_scan_lac()

        lac = session.query(Cell).filter(
            Cell.lac == 1,
            Cell.cid == CELLID_LAC).first()

        # We produced a sequence of 0.2-degree-on-a-side
        # cell bounding boxes centered at [0, 1, 2, ..., 9]
        # degrees. So the lower-left corner is at (-0.1, -0.1)
        # and the upper-right corner is at (9.1, 9.1)
        # we should therefore see a LAC centroid at (4.5, 4.5)
        # with a range of 723,001m
        self.assertEqual(lac.lat, 4.5)
        self.assertEqual(lac.lon, 4.5)
        self.assertEqual(lac.range, 723001)
        self.assertEqual(lac.created.date(), util.utcnow().date())
        self.assertEqual(lac.new_measures, 0)
        self.assertEqual(lac.total_measures, 0)


class TestWifi(CeleryTestCase):

    def test_blacklist_moving_wifis(self):
        now = util.utcnow()
        long_ago = now - timedelta(days=40)
        session = self.db_master_session
        k1 = "ab1234567890"
        k2 = "bc1234567890"
        k3 = "cd1234567890"
        k4 = "de1234567890"
        k5 = "ef1234567890"
        k6 = "fa1234567890"

        keys = set([k1, k2, k3, k4, k5, k6])

        # keys k2, k3 and k4 are expected to be detected as moving
        data = [
            # a wifi with an entry but no prior position
            Wifi(key=k1, new_measures=3, total_measures=0),
            WifiMeasure(lat=1.001, lon=1.001, key=k1),
            WifiMeasure(lat=1.002, lon=1.005, key=k1),
            WifiMeasure(lat=1.003, lon=1.009, key=k1),
            # a wifi with a prior known position
            Wifi(lat=2.0, lon=2.0, key=k2,
                 new_measures=2, total_measures=1),
            WifiMeasure(lat=2.01, lon=2, key=k2),
            WifiMeasure(lat=2.07, lon=2, key=k2),
            # a wifi with a very different prior position
            Wifi(lat=1.0, lon=1.0, key=k3,
                 new_measures=2, total_measures=1),
            WifiMeasure(lat=3.0, lon=3.0, key=k3),
            WifiMeasure(lat=-3.0, lon=3.0, key=k3),
            # another wifi with a prior known position (and negative lat)
            Wifi(lat=-4.0, lon=4.0, key=k4,
                 new_measures=2, total_measures=1),
            WifiMeasure(lat=-4.1, lon=4, key=k4),
            WifiMeasure(lat=-4.16, lon=4, key=k4),
            # an already blacklisted wifi
            WifiBlacklist(key=k5),
            WifiMeasure(lat=5.0, lon=5.0, key=k5),
            WifiMeasure(lat=5.1, lon=5.0, key=k5),
            # a wifi with an old different record we ignore, position
            # estimate has been updated since
            Wifi(lat=6.0, lon=6.0, key=k6,
                 new_measures=2, total_measures=1),
            WifiMeasure(lat=6.9, lon=6.9, key=k6, time=long_ago),
            WifiMeasure(lat=6.0, lon=6.0, key=k6),
            WifiMeasure(lat=6.001, lon=6.0, key=k6),
        ]
        session.add_all(data)
        session.commit()

        result = location_update_wifi.delay(min_new=1)
        self.assertEqual(result.get(), (5, 3))

        black = session.query(WifiBlacklist).all()
        self.assertEqual(set([b.key for b in black]), set([k2, k3, k4, k5]))

        measures = session.query(WifiMeasure).all()
        self.assertEqual(len(measures), 14)
        self.assertEqual(set([m.key for m in measures]), keys)

        # test duplicate call
        result = location_update_wifi.delay(min_new=1)
        self.assertEqual(result.get(), 0)

        self.check_stats(
            total=6,
            timer=[
                # We made duplicate calls
                ('task.data.location_update_wifi', 2),
                # One of those would've scheduled a remove_wifi task
                ('task.data.remove_wifi', 1)
            ],
            gauge=[
                ('task.data.location_update_wifi.new_measures_1_100', 2),
            ])

    def test_location_update_wifi(self):
        now = util.utcnow()
        before = now - timedelta(days=1)
        session = self.db_master_session
        k1 = "ab1234567890"
        k2 = "cd1234567890"
        data = [
            Wifi(key=k1, new_measures=3, total_measures=3),
            WifiMeasure(lat=1.0, lon=1.0, key=k1),
            WifiMeasure(lat=1.002, lon=1.003, key=k1),
            WifiMeasure(lat=1.004, lon=1.006, key=k1),
            Wifi(key=k2, lat=2.0, lon=2.0,
                 new_measures=2, total_measures=4),
            # the lat/lon is bogus and mismatches the line above on purpose
            # to make sure old measures are skipped
            WifiMeasure(lat=-1.0, lon=-1.0, key=k2, created=before),
            WifiMeasure(lat=-1.0, lon=-1.0, key=k2, created=before),
            WifiMeasure(lat=2.002, lon=2.004, key=k2, created=now),
            WifiMeasure(lat=2.002, lon=2.004, key=k2, created=now),
        ]
        session.add_all(data)
        session.commit()

        result = location_update_wifi.delay(min_new=1)
        self.assertEqual(result.get(), (2, 0))
        self.check_stats(
            total=2,
            timer=['task.data.location_update_wifi'],
            gauge=['task.data.location_update_wifi.new_measures_1_100'],
        )

        wifis = dict(session.query(Wifi.key, Wifi).all())
        self.assertEqual(set(wifis.keys()), set([k1, k2]))

        self.assertEqual(wifis[k1].lat, 1.002)
        self.assertEqual(wifis[k1].lon, 1.003)
        self.assertEqual(wifis[k1].new_measures, 0)

        self.assertEqual(wifis[k2].lat, 2.001)
        self.assertEqual(wifis[k2].lon, 2.002)
        self.assertEqual(wifis[k2].new_measures, 0)

    def test_max_min_range_update(self):
        session = self.db_master_session
        k1 = "ab1234567890"
        k2 = "cd1234567890"
        data = [
            Wifi(key=k1, new_measures=2, total_measures=2),
            WifiMeasure(lat=1.0, lon=1.0, key=k1),
            WifiMeasure(lat=1.002, lon=1.004, key=k1),
            Wifi(key=k2, lat=2.0, lon=-2.0,
                 max_lat=2.001, min_lat=1.999,
                 max_lon=-1.999, min_lon=-2.001,
                 new_measures=2, total_measures=4),
            WifiMeasure(lat=2.002, lon=-2.004, key=k2),
            WifiMeasure(lat=1.998, lon=-1.996, key=k2),
        ]
        session.add_all(data)
        session.commit()

        result = location_update_wifi.delay(min_new=1)
        self.assertEqual(result.get(), (2, 0))

        wifis = dict(session.query(Wifi.key, Wifi).all())
        self.assertEqual(set(wifis.keys()), set([k1, k2]))

        self.assertEqual(wifis[k1].lat, 1.001)
        self.assertEqual(wifis[k1].max_lat, 1.002)
        self.assertEqual(wifis[k1].min_lat, 1.0)
        self.assertEqual(wifis[k1].lon, 1.002)
        self.assertEqual(wifis[k1].max_lon, 1.004)
        self.assertEqual(wifis[k1].min_lon, 1.0)

        self.assertEqual(wifis[k2].lat, 2.0)
        self.assertEqual(wifis[k2].max_lat, 2.002)
        self.assertEqual(wifis[k2].min_lat, 1.998)
        self.assertEqual(wifis[k2].lon, -2.0)
        self.assertEqual(wifis[k2].max_lon, -1.996)
        self.assertEqual(wifis[k2].min_lon, -2.004)

        # independent calculation: the k1 bounding box is
        # (1.000, 1.000) to (1.002, 1.004), with centroid
        # at (1.001, 1.002); worst distance from centroid
        # to any corner is 249m
        self.assertEqual(wifis[k1].range, 249)

        # independent calculation: the k2 bounding box is
        # (1.998, -2.004) to (2.002, -1.996), with centroid
        # at (2.000, 2.000); worst distance from centroid
        # to any corner is 497m
        self.assertEqual(wifis[k2].range, 497)

    def test_remove_wifi(self):
        session = self.db_master_session
        measures = []
        wifi_keys = [{'key': "a%s1234567890" % i} for i in range(5)]
        m1 = 1.0
        m2 = 2.0
        for key in wifi_keys:
            key = key['key']
            measures.append(Wifi(key=key))
            measures.append(WifiMeasure(lat=m1, lon=m1, key=key))
            measures.append(WifiMeasure(lat=m2, lon=m2, key=key))
        session.add_all(measures)
        session.flush()

        result = remove_wifi.delay(wifi_keys[:2])
        self.assertEqual(result.get(), 2)

        wifis = session.query(Wifi).all()
        self.assertEqual(len(wifis), 3)

        result = remove_wifi.delay(wifi_keys)
        self.assertEqual(result.get(), 3)

        result = remove_wifi.delay(wifi_keys)
        self.assertEqual(result.get(), 0)

        wifis = session.query(Wifi).all()
        self.assertEqual(len(wifis), 0)
