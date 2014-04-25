from datetime import datetime
from datetime import timedelta

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


class TestCellLocationUpdate(CeleryTestCase):

    def test_cell_location_update(self):
        from ichnaea.tasks import cell_location_update
        now = datetime.utcnow()
        before = now - timedelta(days=1)
        session = self.db_master_session
        k1 = dict(radio=1, mcc=1, mnc=2, lac=3, cid=4)
        k2 = dict(radio=1, mcc=1, mnc=2, lac=6, cid=8)
        k3 = dict(radio=1, mcc=1, mnc=2, lac=-1, cid=-1)
        data = [
            Cell(new_measures=3, total_measures=5, **k1),
            CellMeasure(lat=10000000, lon=10000000, **k1),
            CellMeasure(lat=10020000, lon=10030000, **k1),
            CellMeasure(lat=10040000, lon=10060000, **k1),
            # The lac, cid are invalid and should be skipped
            CellMeasure(lat=15000000, lon=15000000, **k3),
            CellMeasure(lat=15020000, lon=15030000, **k3),

            Cell(lat=20000000, lon=20000000,
                 new_measures=2, total_measures=4, **k2),
            # the lat/lon is bogus and mismatches the line above on purpose
            # to make sure old measures are skipped
            CellMeasure(lat=-10000000, lon=-10000000, created=before, **k2),
            CellMeasure(lat=-10000000, lon=-10000000, created=before, **k2),
            CellMeasure(lat=20020000, lon=20040000, **k2),
            CellMeasure(lat=20020000, lon=20040000, **k2),

        ]
        session.add_all(data)
        session.commit()

        result = cell_location_update.delay(min_new=1)
        self.assertEqual(result.get(), (2, 0))

        cells = session.query(Cell).filter(Cell.cid != CELLID_LAC).all()
        self.assertEqual(len(cells), 2)
        self.assertEqual([c.new_measures for c in cells], [0, 0])
        for cell in cells:
            if cell.cid == 4:
                self.assertEqual(cell.lat, 10020000)
                self.assertEqual(cell.lon, 10030000)
            elif cell.cid == 8:
                self.assertEqual(cell.lat, 20010000)
                self.assertEqual(cell.lon, 20020000)

    def test_backfill_cell_location_update(self):
        from ichnaea.tasks import backfill_cell_location_update
        session = self.db_master_session
        k1 = dict(radio=1, mcc=1, mnc=2, lac=3, cid=4)
        data = [
            Cell(lat=10010000, lon=10010000, new_measures=0,
                 total_measures=1, **k1),
            CellMeasure(lat=10000000, lon=10000000, **k1),
            CellMeasure(lat=10050000, lon=10080000, **k1),
        ]
        session.add_all(data)
        session.commit()

        query = session.query(CellMeasure.id)
        cm_ids = [x[0] for x in query.all()]

        # TODO: refactor this to be constants in the method
        new_measures = [((1, 1, 2, 3, 4), cm_ids)]

        result = backfill_cell_location_update.delay(new_measures)
        self.assertEqual(result.get(), (1, 0))

        cells = session.query(Cell).filter(Cell.cid != CELLID_LAC).all()
        self.assertEqual(len(cells), 1)
        cell = cells[0]
        self.assertEqual(cell.lat, 10020000)
        self.assertEqual(cell.lon, 10030000)
        self.assertEqual(cell.new_measures, 0)
        self.assertEqual(cell.total_measures, 3)

    def test_cell_max_min_range_update(self):
        from ichnaea.tasks import cell_location_update
        session = self.db_master_session

        k1 = dict(radio=1, mcc=1, mnc=2, lac=3, cid=4)
        data = [
            Cell(lat=10010000, lon=-10010000,
                 max_lat=10020000, min_lat=10000000,
                 max_lon=-10000000, min_lon=-10020000,
                 new_measures=2, total_measures=4, **k1),
            CellMeasure(lat=10010000, lon=-10030000, **k1),
            CellMeasure(lat=10050000, lon=-10070000, **k1),
        ]
        session.add_all(data)
        session.commit()

        result = cell_location_update.delay(min_new=1)
        self.assertEqual(result.get(), (1, 0))

        cells = session.query(Cell).filter(Cell.cid != CELLID_LAC).all()
        self.assertEqual(len(cells), 1)
        cell = cells[0]
        self.assertEqual(cell.lat, 10020000)
        self.assertEqual(cell.max_lat, 10050000)
        self.assertEqual(cell.min_lat, 10000000)
        self.assertEqual(cell.lon, -10030000)
        self.assertEqual(cell.max_lon, -10000000)
        self.assertEqual(cell.min_lon, -10070000)

        # independent calculation: the cell bounding box is
        # (1.000, -1.007) to (1.005, -1.000), and distance
        # between those is 956.43m, int(round(dist/2.0)) is 478m
        self.assertEqual(cell.range, 478)

    def test_blacklist_moving_cells(self):
        from ichnaea.tasks import cell_location_update
        now = datetime.utcnow()
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
            CellMeasure(lat=10010000, lon=10010000, **k1),
            CellMeasure(lat=10020000, lon=10050000, **k1),
            CellMeasure(lat=10030000, lon=10090000, **k1),
            # a cell with a prior known position
            Cell(lat=20000000, lon=20000000,
                 new_measures=2, total_measures=1, **k2),
            CellMeasure(lat=20000000, lon=20000000, **k2),
            CellMeasure(lat=40000000, lon=20000000, **k2),
            # a cell with a very different prior position
            Cell(lat=10000000, lon=10000000,
                 new_measures=2, total_measures=1, **k3),
            CellMeasure(lat=30000000, lon=30000000, **k3),
            CellMeasure(lat=-30000000, lon=30000000, **k3),
            # another cell with a prior known position (and negative lat)
            Cell(lat=-40000000, lon=40000000,
                 new_measures=2, total_measures=1, **k4),
            CellMeasure(lat=-40000000, lon=40000000, **k4),
            CellMeasure(lat=-60000000, lon=40000000, **k4),
            # an already blacklisted cell
            CellBlacklist(**k5),
            CellMeasure(lat=50000000, lon=50000000, **k5),
            CellMeasure(lat=80000000, lon=50000000, **k5),
            # a cell with an old different record we ignore, position
            # estimate has been updated since
            Cell(lat=60000000, lon=60000000,
                 new_measures=2, total_measures=1, **k6),
            CellMeasure(lat=69000000, lon=69000000, created=long_ago, **k6),
            CellMeasure(lat=60000000, lon=60000000, **k6),
            CellMeasure(lat=60010000, lon=60000000, **k6),
        ]
        session.add_all(data)
        session.commit()

        result = cell_location_update.delay(min_new=1)
        self.assertEqual(result.get(), (5, 3))

        black = session.query(CellBlacklist).all()
        self.assertEqual(set([to_cellkey(b) for b in black]),
                         set([CellKey(**k) for k in [k2, k3, k4, k5]]))

        measures = session.query(CellMeasure).all()
        self.assertEqual(len(measures), 14)
        self.assertEqual(set([to_cellkey(m) for m in measures]), keys)

        # test duplicate call
        result = cell_location_update.delay(min_new=1)
        self.assertEqual(result.get(), 0)

        self.check_expected_heka_messages(
            total=4,
            timer=[
                # We made duplicate calls
                ('task.cell_location_update', 2),

                # One of those would've scheduled a remove_cell task
                ('task.remove_cell', 1)
            ])

    def add_line_of_cells_and_scan_lac(self):
        from ichnaea.tasks import cell_location_update, scan_lacs
        session = self.db_master_session
        session.commit()
        big = 10000000
        small = big / 10
        keys = dict(radio=1, mcc=1, mnc=1, lac=1)
        measures = [
            CellMeasure(lat=ctr + xd, lon=ctr + yd, cid=cell, **keys)
            for cell in range(0, 10)
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
            for cell in range(0, 10)
            for ctr in [cell * big]
        ]

        session.add_all(cells)
        session.commit()
        result = cell_location_update.delay(min_new=0,
                                            max_new=9999,
                                            batch=len(measures))
        self.assertEqual(result.get(), (len(cells), 0))
        scan_lacs.delay()
        lac = session.query(Cell).filter(
            Cell.lac == 1,
            Cell.cid == CELLID_LAC).first()

        # We produced a sequence of 0.2-degree-on-a-side
        # cell bounding boxes centered at [0, 1, 2, ..., 9]
        # degrees. So the lower-left corner is at (-0.1, -0.1)
        # and the upper-right corner is at (9.1, 9.1)
        # we should therefore see a LAC centroid at (4.5, 4.5)
        # with a range of 723,001m
        self.assertEqual(lac.lat, 45000000)
        self.assertEqual(lac.lon, 45000000)
        self.assertEqual(lac.range, 723001)

    def test_cell_lac_update(self):
        self.add_line_of_cells_and_scan_lac()

    def test_cell_lac_asymmetric(self):
        from ichnaea.tasks import cell_location_update, scan_lacs
        session = self.db_master_session
        big = 1000000
        small = big / 10
        keys = dict(radio=1, mcc=1, mnc=1, lac=1)
        measures = [
            CellMeasure(lat=ctr + xd, lon=ctr + yd, cid=cell, **keys)
            for cell in range(0, 6)
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
            for cell in range(0, 6)
            for ctr in [(2 ** cell) * big]
        ]

        session.add_all(cells)
        session.commit()
        result = cell_location_update.delay(min_new=0,
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
        self.assertEqual(lac.lat, 10500000)
        self.assertEqual(lac.lon, 10500000)
        self.assertEqual(lac.range, 339540)

    def test_cell_removal_updates_lac(self):
        from ichnaea.tasks import remove_cell, scan_lacs

        session = self.db_master_session
        keys = dict(radio=1, mcc=1, mnc=1, lac=1)

        # setup: build LAC as above
        self.add_line_of_cells_and_scan_lac()

        # confirm we got one
        lac = session.query(Cell).filter(
            Cell.lac == 1,
            Cell.cid == CELLID_LAC).first()

        self.assertEqual(lac.lat, 45000000)
        self.assertEqual(lac.lon, 45000000)
        self.assertEqual(lac.range, 723001)

        # Remove cells one by one checking that the LAC
        # changes shape along the way.
        steps = [
            ((50000000, 50000000), 644242),
            ((55000000, 55000000), 565475),
            ((60000000, 60000000), 486721),
            ((65000000, 65000000), 408000),
            ((70000000, 70000000), 329334),
            ((75000000, 75000000), 250743),
            ((80000000, 80000000), 172249),
            ((85000000, 85000000), 93871),
            ((90000000, 90000000), 15630),
        ]
        for i in range(0, 9):
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


class TestWifiLocationUpdate(CeleryTestCase):

    def test_wifi_location_update(self):
        from ichnaea.tasks import wifi_location_update
        now = datetime.utcnow()
        before = now - timedelta(days=1)
        session = self.db_master_session
        k1 = "ab1234567890"
        k2 = "cd1234567890"
        data = [
            Wifi(key=k1, new_measures=3, total_measures=3),
            WifiMeasure(lat=10000000, lon=10000000, key=k1),
            WifiMeasure(lat=10020000, lon=10030000, key=k1),
            WifiMeasure(lat=10040000, lon=10060000, key=k1),
            Wifi(key=k2, lat=20000000, lon=20000000,
                 new_measures=2, total_measures=4),
            # the lat/lon is bogus and mismatches the line above on purpose
            # to make sure old measures are skipped
            WifiMeasure(lat=-10000000, lon=-10000000, key=k2, created=before),
            WifiMeasure(lat=-10000000, lon=-10000000, key=k2, created=before),
            WifiMeasure(lat=20020000, lon=20040000, key=k2, created=now),
            WifiMeasure(lat=20020000, lon=20040000, key=k2, created=now),
        ]
        session.add_all(data)
        session.commit()

        result = wifi_location_update.delay(min_new=1)
        self.assertEqual(result.get(), (2, 0))

        wifis = dict(session.query(Wifi.key, Wifi).all())
        self.assertEqual(set(wifis.keys()), set([k1, k2]))

        self.assertEqual(wifis[k1].lat, 10020000)
        self.assertEqual(wifis[k1].lon, 10030000)
        self.assertEqual(wifis[k1].new_measures, 0)

        self.assertEqual(wifis[k2].lat, 20010000)
        self.assertEqual(wifis[k2].lon, 20020000)
        self.assertEqual(wifis[k2].new_measures, 0)

    def test_wifi_max_min_range_update(self):
        from ichnaea.tasks import wifi_location_update
        session = self.db_master_session
        k1 = "ab1234567890"
        k2 = "cd1234567890"
        data = [
            Wifi(key=k1, new_measures=2, total_measures=2),
            WifiMeasure(lat=10000000, lon=10000000, key=k1),
            WifiMeasure(lat=10020000, lon=10040000, key=k1),
            Wifi(key=k2, lat=20000000, lon=-20000000,
                 max_lat=20010000, min_lat=19990000,
                 max_lon=-19990000, min_lon=-20010000,
                 new_measures=2, total_measures=4),
            WifiMeasure(lat=20020000, lon=-20040000, key=k2),
            WifiMeasure(lat=19980000, lon=-19960000, key=k2),
        ]
        session.add_all(data)
        session.commit()

        result = wifi_location_update.delay(min_new=1)
        self.assertEqual(result.get(), (2, 0))

        wifis = dict(session.query(Wifi.key, Wifi).all())
        self.assertEqual(set(wifis.keys()), set([k1, k2]))

        self.assertEqual(wifis[k1].lat, 10010000)
        self.assertEqual(wifis[k1].max_lat, 10020000)
        self.assertEqual(wifis[k1].min_lat, 10000000)
        self.assertEqual(wifis[k1].lon, 10020000)
        self.assertEqual(wifis[k1].max_lon, 10040000)
        self.assertEqual(wifis[k1].min_lon, 10000000)

        self.assertEqual(wifis[k2].lat, 20000000)
        self.assertEqual(wifis[k2].max_lat, 20020000)
        self.assertEqual(wifis[k2].min_lat, 19980000)
        self.assertEqual(wifis[k2].lon, -20000000)
        self.assertEqual(wifis[k2].max_lon, -19960000)
        self.assertEqual(wifis[k2].min_lon, -20040000)

        # independent calculation: the k1 bounding box is
        # (1.000, 1.000) to (1.002, 1.004), and distance
        # between those is 497.21m, int(round(dist/2.0)) is 249m
        self.assertEqual(wifis[k1].range, 249)

        # independent calculation: the k2 bounding box is
        # (1.998, -2.004) to (2.002, -1.996), and distance
        # between those is 994.07m, int(round(dist/2.0)) is 497m
        self.assertEqual(wifis[k2].range, 497)

    def test_blacklist_moving_wifis(self):
        from ichnaea.tasks import wifi_location_update
        now = datetime.utcnow()
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
            WifiMeasure(lat=10010000, lon=10010000, key=k1),
            WifiMeasure(lat=10020000, lon=10050000, key=k1),
            WifiMeasure(lat=10030000, lon=10090000, key=k1),
            # a wifi with a prior known position
            Wifi(lat=20000000, lon=20000000, key=k2,
                 new_measures=2, total_measures=1),
            WifiMeasure(lat=20100000, lon=20000000, key=k2),
            WifiMeasure(lat=20700000, lon=20000000, key=k2),
            # a wifi with a very different prior position
            Wifi(lat=10000000, lon=10000000, key=k3,
                 new_measures=2, total_measures=1),
            WifiMeasure(lat=30000000, lon=30000000, key=k3),
            WifiMeasure(lat=-30000000, lon=30000000, key=k3),
            # another wifi with a prior known position (and negative lat)
            Wifi(lat=-40000000, lon=40000000, key=k4,
                 new_measures=2, total_measures=1),
            WifiMeasure(lat=-41000000, lon=40000000, key=k4),
            WifiMeasure(lat=-41600000, lon=40000000, key=k4),
            # an already blacklisted wifi
            WifiBlacklist(key=k5),
            WifiMeasure(lat=50000000, lon=50000000, key=k5),
            WifiMeasure(lat=51000000, lon=50000000, key=k5),
            # a wifi with an old different record we ignore, position
            # estimate has been updated since
            Wifi(lat=60000000, lon=60000000, key=k6,
                 new_measures=2, total_measures=1),
            WifiMeasure(lat=69000000, lon=69000000, key=k6, created=long_ago),
            WifiMeasure(lat=60000000, lon=60000000, key=k6),
            WifiMeasure(lat=60010000, lon=60000000, key=k6),
        ]
        session.add_all(data)
        session.commit()

        result = wifi_location_update.delay(min_new=1)
        self.assertEqual(result.get(), (5, 3))

        black = session.query(WifiBlacklist).all()
        self.assertEqual(set([b.key for b in black]), set([k2, k3, k4, k5]))

        measures = session.query(WifiMeasure).all()
        self.assertEqual(len(measures), 14)
        self.assertEqual(set([m.key for m in measures]), keys)

        # test duplicate call
        result = wifi_location_update.delay(min_new=1)
        self.assertEqual(result.get(), 0)

        self.check_expected_heka_messages(
            total=4,
            timer=[
                # We made duplicate calls
                ('task.wifi_location_update', 2),

                # One of those would've scheduled a remove_wifi task
                ('task.remove_wifi', 1)
            ])

    def test_remove_wifi(self):
        from ichnaea.tasks import remove_wifi
        session = self.db_master_session
        measures = []
        wifi_keys = ["a%s1234567890" % i for i in range(5)]
        m1 = 10000000
        m2 = 10000000
        for key in wifi_keys:
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

    def check_trim_excessive_data(self, unique_model, measure_model,
                                  trim_func, kinit, kcmp, delstat):
        """
        Synthesize many measurements and repeatedly run trim function
        with a few smaller and smaller sizes, confirming that correct
        measurements are discarded at each step and counters adjusted.
        """
        session = self.db_master_session
        measures = []
        backdate = datetime.utcnow() - timedelta(days=10)
        keys = range(3)
        measures_per_key = 8
        m1 = 10000000
        m2 = 20000000
        session.query(unique_model).delete()
        session.query(measure_model).delete()
        session.flush()
        for k in keys:
            kargs = kinit(k)
            measures.append(unique_model(lat=(m1 + m2) / 2, lon=(m1 + m2) / 2,
                                         new_measures=measures_per_key,
                                         total_measures=measures_per_key * 2,
                                         **kargs))
            kargs['created'] = backdate
            kargs['time'] = backdate
            for i in range(measures_per_key):
                measures.append(measure_model(lat=m1 + i, lon=m1 + i, **kargs))
                measures.append(measure_model(lat=m2 + i, lon=m2 + i, **kargs))
        session.add_all(measures)
        session.flush()

        measures = session.query(measure_model).count()
        self.assertEqual(measures, measures_per_key * 2 * len(keys))

        def trim_and_check(keep):
            from ichnaea.content.tasks import get_curr_stat

            # trim model to 'keep' measures per key
            result = trim_func.delay(keep)
            result.get()

            # check that exactly the rows expected were kept
            measures = session.query(measure_model).all()
            self.assertEqual(len(measures), len(keys) * keep)
            for k in keys:
                for i in range(measures_per_key - keep / 2, measures_per_key):
                    self.assertTrue(any(m.lat == m1 + i and
                                        m.lat == m1 + i and
                                        kcmp(m, k)
                                        for m in measures))
                    self.assertTrue(any(m.lat == m2 + i and
                                        m.lat == m2 + i and
                                        kcmp(m, k)
                                        for m in measures))

            stations = session.query(unique_model).all()
            for s in stations:
                self.assertTrue(s.new_measures <= s.total_measures)

            # check that the deletion stat was updated
            self.assertEqual(get_curr_stat(session, delstat),
                             len(keys) * (2 * measures_per_key - keep))

        trim_and_check(6)
        trim_and_check(4)
        trim_and_check(2)

    def check_no_trim_young_data(self, unique_model, measure_model,
                                 trim_func, kinit, delstat):
        """
        Check that a trim function run against young data leaves it alone.
        """
        from ichnaea.content.tasks import get_curr_stat

        session = self.db_master_session
        measures = []
        keys = range(3)
        measures_per_key = 4
        m1 = 10000000
        m2 = 20000000
        session.query(unique_model).delete()
        session.query(measure_model).delete()
        session.flush()
        for k in keys:
            kargs = kinit(k)
            measures.append(unique_model(lat=(m1 + m2) / 2, lon=(m1 + m2) / 2,
                                         total_measures=measures_per_key * 2,
                                         **kargs))
            for i in range(measures_per_key):
                measures.append(measure_model(lat=m1 + i, lon=m1 + i, **kargs))
                measures.append(measure_model(lat=m2 + i, lon=m2 + i, **kargs))
        session.add_all(measures)
        session.flush()

        measures = session.query(measure_model).count()
        self.assertEqual(measures, measures_per_key * 2 * len(keys))

        dels = get_curr_stat(session, delstat)

        result = trim_func.delay(2)
        result.get()

        # check that all data was preserved
        measures = session.query(measure_model).count()
        self.assertEqual(measures, measures_per_key * 2 * len(keys))

        # check that the deletion stat is unchanged
        self.assertEqual(get_curr_stat(session, delstat), dels)

    def test_cell_trim_excessive_data(self):
        from ichnaea.tasks import cell_trim_excessive_data
        self.check_trim_excessive_data(unique_model=Cell,
                                       measure_model=CellMeasure,
                                       trim_func=cell_trim_excessive_data,
                                       kinit=lambda k: {'radio': k,
                                                        'mcc': k,
                                                        'mnc': k,
                                                        'lac': k,
                                                        'cid': k, },
                                       kcmp=lambda m, k: (m.radio == k and
                                                          m.mcc == k and
                                                          m.mnc == k and
                                                          m.lac == k and
                                                          m.cid == k),
                                       delstat='deleted_cell')

    def test_cell_no_trim_young_data(self):
        from ichnaea.tasks import cell_trim_excessive_data
        self.check_no_trim_young_data(unique_model=Cell,
                                      measure_model=CellMeasure,
                                      trim_func=cell_trim_excessive_data,
                                      kinit=lambda k: {'radio': k,
                                                       'mcc': k,
                                                       'mnc': k,
                                                       'lac': k,
                                                       'cid': k, },
                                      delstat='deleted_cell')

    def test_wifi_trim_excessive_data(self):
        from ichnaea.tasks import wifi_trim_excessive_data
        self.check_trim_excessive_data(unique_model=Wifi,
                                       measure_model=WifiMeasure,
                                       trim_func=wifi_trim_excessive_data,
                                       kinit=lambda k: {'key': str(k)},
                                       kcmp=lambda m, k: m.key == str(k),
                                       delstat='deleted_wifi')

    def test_wifi_no_trim_young_data(self):
        from ichnaea.tasks import wifi_trim_excessive_data
        self.check_no_trim_young_data(unique_model=Wifi,
                                      measure_model=WifiMeasure,
                                      trim_func=wifi_trim_excessive_data,
                                      kinit=lambda k: {'key': str(k)},
                                      delstat='deleted_wifi')
