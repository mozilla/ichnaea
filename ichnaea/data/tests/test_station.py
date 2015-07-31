from datetime import timedelta

from ichnaea.constants import (
    PERMANENT_BLOCKLIST_THRESHOLD,
    TEMPORARY_BLOCKLIST_DURATION,
)
from ichnaea.data.tasks import (
    update_cell,
    update_wifi,
    remove_wifi,
    scan_areas,
)
from ichnaea.models import (
    Cell,
    CellArea,
    CellBlocklist,
    StatCounter,
    StatKey,
    Wifi,
    WifiBlocklist,
)
from ichnaea.tests.base import CeleryTestCase
from ichnaea.tests.factories import (
    CellFactory,
    CellBlocklistFactory,
    CellObservationFactory,
    WifiFactory,
    WifiBlocklistFactory,
    WifiObservationFactory,
)
from ichnaea import util


class StationTest(CeleryTestCase):

    def _compare_sets(self, one, two):
        self.assertEqual(set(one), set(two))

    def check_statcounter(self, stat_key, value):
        stat_counter = StatCounter(stat_key, util.utcnow())
        self.assertEqual(stat_counter.get(self.redis_client), value)


class TestCell(StationTest):

    def setUp(self):
        super(TestCell, self).setUp()
        self.data_queue = self.celery_app.data_queues['update_cell']

    def test_blocklist(self):
        now = util.utcnow()
        observations = CellObservationFactory.build_batch(3)
        obs = observations[0]

        block = CellBlocklist(
            radio=obs.radio, mcc=obs.mcc, mnc=obs.mnc,
            lac=obs.lac, cid=obs.cid,
            time=now, count=1,
        )
        self.session.add(block)
        self.session.flush()

        self.data_queue.enqueue(observations)
        self.assertEqual(self.data_queue.size(), 3)
        update_cell.delay().get()

        cells = self.session.query(Cell).all()
        self.assertEqual(len(cells), 2)

        self.check_statcounter(StatKey.cell, 2)
        self.check_statcounter(StatKey.unique_cell, 2)

    def test_created_from_blocklist_time(self):
        now = util.utcnow()
        last_week = now - TEMPORARY_BLOCKLIST_DURATION - timedelta(days=1)

        obs = CellObservationFactory.build()
        self.session.add(
            CellBlocklist(time=last_week, count=1,
                          radio=obs.radio, mcc=obs.mcc,
                          mnc=obs.mnc, lac=obs.lac, cid=obs.cid))
        self.session.flush()

        # add a new entry for the previously blocklisted cell
        self.data_queue.enqueue([obs])
        self.assertEqual(self.data_queue.size(), 1)
        update_cell.delay().get()

        # the cell was inserted again
        cells = self.session.query(Cell).all()
        self.assertEqual(len(cells), 1)

        # and the creation date was set to the date of the blocklist entry
        self.assertEqual(cells[0].created, last_week)

        self.check_statcounter(StatKey.cell, 1)
        self.check_statcounter(StatKey.unique_cell, 0)

    def test_blocklist_moving_cells(self):
        now = util.utcnow()
        obs = []
        obs_factory = CellObservationFactory
        moving = set()
        cells = CellFactory.create_batch(4)
        cells.append(CellFactory.build())
        # a cell with an entry but no prior position
        cell = cells[0]
        cell_key = cell.hashkey().__dict__
        cell.total_measures = 0
        obs.extend([
            obs_factory(lat=cell.lat + 0.01,
                        lon=cell.lon + 0.01, **cell_key),
            obs_factory(lat=cell.lat + 0.02,
                        lon=cell.lon + 0.05, **cell_key),
            obs_factory(lat=cell.lat + 0.03,
                        lon=cell.lon + 0.09, **cell_key),
        ])
        cell.lat = None
        cell.lon = None
        # a cell with a prior known position
        cell = cells[1]
        cell_key = cell.hashkey().__dict__
        cell.total_measures = 1
        cell.lat += 0.1
        obs.extend([
            obs_factory(lat=cell.lat + 1.0,
                        lon=cell.lon, **cell_key),
            obs_factory(lat=cell.lat + 3.0,
                        lon=cell.lon, **cell_key),
        ])
        moving.add(cell.hashkey())
        # a cell with a very different prior position
        cell = cells[2]
        cell_key = cell.hashkey().__dict__
        cell.total_measures = 1
        obs.extend([
            obs_factory(lat=cell.lat + 4.0,
                        lon=cell.lon, **cell_key),
            obs_factory(lat=cell.lat - 0.1,
                        lon=cell.lon, **cell_key),
        ])
        moving.add(cell.hashkey())
        # another cell with a prior known position (and negative lon)
        cell = cells[3]
        cell_key = cell.hashkey().__dict__
        cell.total_measures = 1
        cell.lon *= -1.0
        obs.extend([
            obs_factory(lat=cell.lat + 1.0,
                        lon=cell.lon, **cell_key),
            obs_factory(lat=cell.lat + 2.0,
                        lon=cell.lon, **cell_key),
        ])
        moving.add(cell.hashkey())
        # an already blocklisted cell
        cell = cells[4]
        cell_key = cell.hashkey().__dict__
        CellBlocklistFactory(time=now, count=1, **cell_key)
        obs.extend([
            obs_factory(lat=cell.lat,
                        lon=cell.lon, **cell_key),
            obs_factory(lat=cell.lat + 3.0,
                        lon=cell.lon, **cell_key),
        ])
        moving.add(cell.hashkey())

        self.data_queue.enqueue(obs)
        self.session.commit()

        result = update_cell.delay()
        self.assertEqual(result.get(), (4, 3))

        block = self.session.query(CellBlocklist).all()
        self.assertEqual(set([b.hashkey() for b in block]), moving)

        # test duplicate call
        result = update_cell.delay()
        self.assertEqual(result.get(), (0, 0))

        self.check_stats(
            timer=[
                # We made duplicate calls
                ('task', 2, ['task:data.update_cell']),
                # One of those would've scheduled a remove_cell task
                ('task', 1, ['task:data.remove_cell'])
            ])

    def test_blocklist_temporary_and_permanent(self):
        # This test simulates a cell that moves once a month, for 2 years.
        # The first 2 * PERMANENT_BLOCKLIST_THRESHOLD (12) moves should be
        # temporary, forgotten after a week; after that it should be
        # permanently blocklisted.

        now = util.utcnow()
        # Station moves between these 4 points, all in the USA:
        points = [
            (40.0, -74.0),  # NYC
            (37.0, -122.0),  # SF
            (47.0, -122.0),  # Seattle
            (25.0, -80.0),  # Miami
        ]

        obs = CellObservationFactory(
            mcc=310, lat=points[0][0], lon=points[0][1])

        N = 4 * PERMANENT_BLOCKLIST_THRESHOLD
        for month in range(0, N):
            days_ago = (N - (month + 1)) * 30
            time = now - timedelta(days=days_ago)

            obs.lat = points[month % 4][0]
            obs.lon = points[month % 4][1]

            # Assuming PERMANENT_BLOCKLIST_THRESHOLD == 6:
            #
            # 0th insert will create the station
            # 1st insert will create first blocklist entry, delete station
            # 2nd insert will recreate the station at new position
            # 3rd insert will update blocklist, re-delete station
            # 4th insert will recreate the station at new position
            # 5th insert will update blocklist, re-delete station
            # 6th insert will recreate the station at new position
            # ...
            # 11th insert will make blocklisting permanent, re-delete station
            # 12th insert will not recreate station
            # 13th insert will not recreate station
            # ...
            # 23rd insert will not recreate station

            blocks = self.session.query(CellBlocklist).all()
            if month < 2:
                self.assertEqual(len(blocks), 0)
            else:
                self.assertEqual(len(blocks), 1)
                # force the blocklist back in time to whenever the
                # observation was supposedly inserted.
                block = blocks[0]
                block.time = time
                self.session.commit()

            if month < N / 2:
                # We still haven't exceeded the threshold, so the
                # observation was admitted.
                self.data_queue.enqueue([obs])
                if month % 2 == 0:
                    # The station was (re)created.
                    self.assertEqual(update_cell.delay().get(), (1, 0))
                    # Rescan lacs to update entries
                    self.assertEqual(scan_areas.delay().get(), 1)
                    # One cell + one cell-LAC record should exist.
                    self.assertEqual(self.session.query(Cell).count(), 1)
                    self.assertEqual(self.session.query(CellArea).count(), 1)
                else:
                    # The station existed and was seen moving,
                    # thereby activating the blocklist and deleting the cell.
                    self.assertEqual(update_cell.delay().get(), (1, 1))
                    # Rescan lacs to delete orphaned lac entry
                    self.assertEqual(scan_areas.delay().get(), 1)
                    if month > 1:
                        self.assertEqual(block.count, ((month + 1) / 2))
                    self.assertEqual(
                        self.session.query(CellBlocklist).count(), 1)
                    self.assertEqual(self.session.query(Cell).count(), 0)

                    # Try adding one more observation
                    # to be sure it is dropped by the now-active blocklist.
                    self.data_queue.enqueue([obs])
                    self.assertEqual(update_cell.delay().get(), (0, 0))
            else:
                # Blocklist has exceeded threshold, gone to permanent mode,
                # so no observation accepted, no stations seen.
                self.data_queue.enqueue([obs])
                self.assertEqual(update_cell.delay().get(), (0, 0))

    def test_update_cell(self):
        now = util.utcnow()
        invalid_key = dict(lac=None, cid=None)
        observations = []

        def obs_factory(**kw):
            obs = CellObservationFactory.build(**kw)
            observations.append(obs)

        cell1 = CellFactory(total_measures=3)
        lat1, lon1 = (cell1.lat, cell1.lon)
        key1 = dict(radio=cell1.radio, lac=cell1.lac, cid=cell1.cid)
        obs_factory(lat=lat1, lon=lon1, created=now, **key1)
        obs_factory(lat=lat1 + 0.004, lon=lon1 + 0.006, created=now, **key1)
        obs_factory(lat=lat1 + 0.006, lon=lon1 + 0.009, created=now, **key1)
        # The lac, cid are invalid and should be skipped
        obs_factory(created=now, **invalid_key)
        obs_factory(created=now, **invalid_key)

        cell2 = CellFactory(lat=lat1 + 1.0, lon=lon1 + 1.0, total_measures=3)
        lat2, lon2 = (cell2.lat, cell2.lon)
        key2 = dict(radio=cell2.radio, lac=cell2.lac, cid=cell2.cid)
        obs_factory(lat=lat2 + 0.001, lon=lon2 + 0.002, created=now, **key2)
        obs_factory(lat=lat2 + 0.003, lon=lon2 + 0.006, created=now, **key2)

        cell3 = CellFactory(total_measures=100000)
        lat3, lon3 = (cell3.lat, cell3.lon)
        key3 = dict(radio=cell3.radio, lac=cell3.lac, cid=cell3.cid)
        for i in range(10):
            obs_factory(lat=lat3 + 1.0, lon=lon3 + 1.0, **key3)

        self.data_queue.enqueue(observations)
        self.session.commit()

        result = update_cell.delay()
        self.assertEqual(result.get(), (3, 0))

        cells = self.session.query(Cell).all()
        self.assertEqual(len(cells), 3)
        for cell in cells:
            if cell.hashkey() == cell1.hashkey():
                self.assertAlmostEqual(cell.lat, lat1 + 0.001667, 6)
                self.assertAlmostEqual(cell.lon, lon1 + 0.0025, 6)
            if cell.hashkey() == cell2.hashkey():
                self.assertAlmostEqual(cell.lat, lat2 + 0.0008, 6)
                self.assertAlmostEqual(cell.lon, lon2 + 0.0016, 6)
            if cell.hashkey() == cell3.hashkey():
                expected_lat = ((lat3 * 1000) + (lat3 + 1.0) * 10) / 1010
                expected_lon = ((lon3 * 1000) + (lon3 + 1.0) * 10) / 1010
                self.assertAlmostEqual(cell.lat, expected_lat, 7)
                self.assertAlmostEqual(cell.lon, expected_lon, 7)

    def test_max_min_range_update(self):
        cell = CellFactory(range=150, total_measures=3)
        cell_lat = cell.lat
        cell_lon = cell.lon
        cell.max_lat = cell.lat + 0.001
        cell.min_lat = cell.lat - 0.001
        cell.max_lon = cell.lon + 0.001
        cell.min_lon = cell.lon - 0.001
        k1 = cell.hashkey().__dict__

        obs_factory = CellObservationFactory
        obs = [
            obs_factory(lat=cell.lat, lon=cell.lon - 0.002, **k1),
            obs_factory(lat=cell.lat + 0.004, lon=cell.lon - 0.006, **k1),
        ]
        self.data_queue.enqueue(obs)
        self.session.commit()

        self.assertEqual(update_cell.delay().get(), (1, 0))

        cells = self.session.query(Cell).all()
        self.assertEqual(len(cells), 1)
        cell = cells[0]
        self.assertAlmostEqual(cell.lat, cell_lat + 0.0008)
        self.assertAlmostEqual(cell.max_lat, cell_lat + 0.004)
        self.assertAlmostEqual(cell.min_lat, cell_lat - 0.001)
        self.assertAlmostEqual(cell.lon, cell_lon - 0.0016)
        self.assertAlmostEqual(cell.max_lon, cell_lon + 0.001)
        self.assertAlmostEqual(cell.min_lon, cell_lon - 0.006)
        self.assertEqual(cell.range, 468)
        self.assertEqual(cell.total_measures, 5)


class TestWifi(StationTest):

    def setUp(self):
        super(TestWifi, self).setUp()
        self.data_queue = self.celery_app.data_queues['update_wifi']

    def test_blocklist(self):
        utcnow = util.utcnow()

        bad_wifi = WifiObservationFactory.build()
        good_wifi = WifiObservationFactory.build()
        block = WifiBlocklist(time=utcnow, count=1, key=bad_wifi.key)
        self.session.add(block)
        self.session.flush()

        observations = [good_wifi, bad_wifi, good_wifi]
        self.data_queue.enqueue(observations)
        self.assertEqual(self.data_queue.size(), 3)
        update_wifi.delay().get()

        wifis = self.session.query(Wifi).all()
        self.assertEqual(len(wifis), 1)
        self._compare_sets([w.key for w in wifis], [good_wifi.key])

        self.check_statcounter(StatKey.wifi, 2)
        self.check_statcounter(StatKey.unique_wifi, 1)

    def test_created_from_blocklist_time(self):
        now = util.utcnow()
        last_week = now - TEMPORARY_BLOCKLIST_DURATION - timedelta(days=1)

        obs = WifiObservationFactory()
        self.session.add(WifiBlocklist(time=last_week, count=1, key=obs.key))
        self.session.flush()

        # add a new entry for the previously blocklisted wifi
        self.data_queue.enqueue([obs])
        self.assertEqual(self.data_queue.size(), 1)
        update_wifi.delay().get()

        # the wifi was inserted again
        wifis = self.session.query(Wifi).all()
        self.assertEqual(len(wifis), 1)

        # and the creation date was set to the date of the blocklist entry
        self.assertEqual(wifis[0].created, last_week)
        self.check_statcounter(StatKey.unique_wifi, 0)

    def test_blocklist_moving_wifis(self):
        now = util.utcnow()
        obs = []
        obs_factory = WifiObservationFactory
        moving = set()
        wifis = WifiFactory.create_batch(4)
        wifis.append(WifiFactory.build())
        # a wifi with an entry but no prior position
        wifi = wifis[0]
        wifi.total_measures = 0
        obs.extend([
            obs_factory(lat=wifi.lat + 0.001,
                        lon=wifi.lon + 0.001, key=wifi.key),
            obs_factory(lat=wifi.lat + 0.002,
                        lon=wifi.lon + 0.005, key=wifi.key),
            obs_factory(lat=wifi.lat + 0.003,
                        lon=wifi.lon + 0.009, key=wifi.key),
        ])
        wifi.lat = None
        wifi.lon = None
        # a wifi with a prior known position
        wifi = wifis[1]
        wifi.total_measures = 1
        wifi.lat += 1.0
        wifi.lon += 1.0
        obs.extend([
            obs_factory(lat=wifi.lat + 0.01,
                        lon=wifi.lon, key=wifi.key),
            obs_factory(lat=wifi.lat + 0.07,
                        lon=wifi.lon, key=wifi.key),
        ])
        moving.add(wifi.hashkey())
        # a wifi with a very different prior position
        wifi = wifis[2]
        wifi.total_measures = 1
        obs.extend([
            obs_factory(lat=wifi.lat + 2.0,
                        lon=wifi.lon + 2.0, key=wifi.key),
            obs_factory(lat=wifi.lat - 4.0,
                        lon=wifi.lon + 2.0, key=wifi.key),
        ])
        moving.add(wifi.hashkey())
        # another wifi with a prior known position (and negative lat)
        wifi = wifis[3]
        wifi.total_measures = 1
        wifi.lat *= -1.0
        obs.extend([
            obs_factory(lat=wifi.lat - 0.1,
                        lon=wifi.lon, key=wifi.key),
            obs_factory(lat=wifi.lat - 0.16,
                        lon=wifi.lon, key=wifi.key),
        ])
        moving.add(wifi.hashkey())
        # an already blocklisted wifi
        wifi = wifis[4]
        WifiBlocklistFactory(key=wifi.key, time=now, count=1)
        obs.extend([
            obs_factory(lat=wifi.lat,
                        lon=wifi.lon, key=wifi.key),
            obs_factory(lat=wifi.lat + 0.1,
                        lon=wifi.lon, key=wifi.key),
        ])
        moving.add(wifi.hashkey())

        self.data_queue.enqueue(obs)
        self.session.commit()

        result = update_wifi.delay()
        self.assertEqual(result.get(), (4, 3))

        block = self.session.query(WifiBlocklist).all()
        self.assertEqual(set([b.hashkey() for b in block]), moving)

        # test duplicate call
        result = update_wifi.delay()
        self.assertEqual(result.get(), (0, 0))

        self.check_stats(
            timer=[
                # We made duplicate calls
                ('task', 2, ['task:data.update_wifi']),
                # One of those would've scheduled a remove_wifi task
                ('task', 1, ['task:data.remove_wifi'])
            ])

    def test_blocklist_temporary_and_permanent(self):
        # This test simulates a wifi that moves once a month, for 2 years.
        # The first 2 * PERMANENT_BLOCKLIST_THRESHOLD (12) moves should be
        # temporary, forgotten after a week; after that it should be
        # permanently blocklisted.

        now = util.utcnow()
        # Station moves between these 4 points, all in the USA:
        points = [
            # NYC
            (40.0, -74.0),
            # SF
            (37.0, -122.0),
            # Seattle
            (47.0, -122.0),
            # Miami
            (25.0, -80.0),
        ]

        obs = WifiObservationFactory()

        N = PERMANENT_BLOCKLIST_THRESHOLD * 4
        for month in range(0, N):
            days_ago = (N - (month + 1)) * 30
            time = now - timedelta(days=days_ago)

            obs.lat = points[month % 4][0]
            obs.lon = points[month % 4][1]

            # Assuming PERMANENT_BLOCKLIST_THRESHOLD == 6:
            #
            # 0th insert will create the station
            # 1st insert will create first blocklist entry, delete station
            # 2nd insert will recreate the station at new position
            # 3rd insert will update blocklist, re-delete station
            # 4th insert will recreate the station at new position
            # 5th insert will update blocklist, re-delete station
            # 6th insert will recreate the station at new position
            # ...
            # 11th insert will make blocklisting permanent, re-delete station
            # 12th insert will not recreate station
            # 13th insert will not recreate station
            # ...
            # 23rd insert will not recreate station

            blocks = self.session.query(WifiBlocklist).all()
            if month < 2:
                self.assertEqual(len(blocks), 0)
            else:
                self.assertEqual(len(blocks), 1)
                # force the blocklist back in time to whenever the
                # observation was supposedly inserted.
                block = blocks[0]
                block.time = time
                self.session.commit()

            if month < N / 2:
                # We still haven't exceeded the threshold, so the
                # observation was admitted.
                self.data_queue.enqueue([obs])
                if month % 2 == 0:
                    # The station was (re)created.
                    self.assertEqual(update_wifi.delay().get(), (1, 0))
                    # One wifi record should exist.
                    self.assertEqual(self.session.query(Wifi).count(), 1)
                else:
                    # The station existed and was seen moving,
                    # thereby activating the blocklist.
                    self.assertEqual(update_wifi.delay().get(), (1, 1))
                    if month > 1:
                        self.assertEqual(block.count, ((month + 1) / 2))
                    self.assertEqual(
                        self.session.query(WifiBlocklist).count(), 1)
                    self.assertEqual(self.session.query(Wifi).count(), 0)

                    # Try adding one more observation
                    # to be sure it is dropped by the now-active blocklist.
                    self.data_queue.enqueue([obs])
                    self.assertEqual(update_wifi.delay().get(), (0, 0))
            else:
                # Blocklist has exceeded threshold, gone to permanent mode,
                # so no observation accepted, no stations seen.
                self.data_queue.enqueue([obs])
                self.assertEqual(update_wifi.delay().get(), (0, 0))

    def test_update_wifi(self):
        obs = []
        obs_factory = WifiObservationFactory
        # first wifi
        wifi1 = WifiFactory(lat=None, lon=None, total_measures=3)
        new_pos = WifiFactory.build()
        lat1, lon1 = (new_pos.lat, new_pos.lon)
        obs.extend([
            obs_factory(lat=lat1,
                        lon=lon1, key=wifi1.key),
            obs_factory(lat=lat1 + 0.002,
                        lon=lon1 + 0.003, key=wifi1.key),
            obs_factory(lat=lat1 + 0.004,
                        lon=lon1 + 0.006, key=wifi1.key),
        ])
        # second wifi
        wifi2 = WifiFactory(lat=lat1 + 1.0, lon=lon1 + 1.0, total_measures=2)
        lat2, lon2 = (wifi2.lat, wifi2.lon)
        obs.extend([
            obs_factory(lat=lat2 + 0.002,
                        lon=lon2 + 0.004, key=wifi2.key),
            obs_factory(lat=lat2 + 0.002,
                        lon=lon2 + 0.004, key=wifi2.key),
        ])
        self.data_queue.enqueue(obs)
        self.session.flush()

        result = update_wifi.delay()
        self.assertEqual(result.get(), (2, 0))
        self.session.refresh(wifi1)
        self.session.refresh(wifi2)

        found = dict(self.session.query(Wifi.key, Wifi).all())
        self.assertEqual(set(found.keys()), set([wifi1.key, wifi2.key]))
        self.assertAlmostEqual(found[wifi1.key].lat, lat1 + 0.002)
        self.assertAlmostEqual(found[wifi1.key].lon, lon1 + 0.003)
        self.assertAlmostEqual(found[wifi2.key].lat, lat2 + 0.001)
        self.assertAlmostEqual(found[wifi2.key].lon, lon2 + 0.002)

    def test_max_min_range_update(self):
        wifi = WifiFactory(range=100, total_measures=4)
        wifi_lat = wifi.lat
        wifi_lon = wifi.lon
        wifi.max_lat = wifi.lat + 0.001
        wifi.min_lat = wifi.lat - 0.001
        wifi.max_lon = wifi.lon + 0.001
        wifi.min_lon = wifi.lon - 0.001

        obs_factory = WifiObservationFactory
        obs = [
            obs_factory(lat=wifi.lat + 0.002,
                        lon=wifi.lon - 0.004, key=wifi.key),
            obs_factory(lat=wifi.lat - 0.002,
                        lon=wifi.lon + 0.01, key=wifi.key),
        ]
        self.data_queue.enqueue(obs)
        self.session.commit()

        self.assertEqual(update_wifi.delay().get(), (1, 0))

        wifis = self.session.query(Wifi).all()
        self.assertEqual(len(wifis), 1)
        wifi = wifis[0]

        self.assertAlmostEqual(wifi.lat, wifi_lat)
        self.assertAlmostEqual(wifi.max_lat, wifi_lat + 0.002)
        self.assertAlmostEqual(wifi.min_lat, wifi_lat - 0.002)
        self.assertAlmostEqual(wifi.lon, wifi_lon + 0.001)
        self.assertAlmostEqual(wifi.max_lon, wifi_lon + 0.01)
        self.assertAlmostEqual(wifi.min_lon, wifi_lon - 0.004)
        self.assertEqual(wifi.range, 662)
        self.assertEqual(wifi.total_measures, 6)

    def test_remove_wifi(self):
        wifis = WifiFactory.create_batch(5)
        wifi_keys = [wifi.key for wifi in wifis]
        self.session.flush()

        result = remove_wifi.delay(wifi_keys[:2])
        self.assertEqual(result.get(), 2)

        wifis = self.session.query(Wifi).all()
        self.assertEqual(len(wifis), 3)

        result = remove_wifi.delay(wifi_keys)
        self.assertEqual(result.get(), 3)

        result = remove_wifi.delay(wifi_keys)
        self.assertEqual(result.get(), 0)

        wifis = self.session.query(Wifi).all()
        self.assertEqual(len(wifis), 0)
