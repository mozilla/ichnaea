from datetime import timedelta

from ichnaea.constants import (
    PERMANENT_BLACKLIST_THRESHOLD,
)
from ichnaea.data.tasks import (
    insert_measures_cell,
    insert_measures_wifi,
    location_update_cell,
    location_update_wifi,
    remove_wifi,
    scan_areas,
)
from ichnaea.models import (
    Cell,
    CellArea,
    CellBlacklist,
    CellObservation,
    Radio,
    Wifi,
    WifiBlacklist,
    WifiObservation,
)
from ichnaea.tests.base import (
    CeleryTestCase,
    USA_MCC, ATT_MNC,
)
from ichnaea.tests.factories import (
    CellFactory,
    CellObservationFactory,
)
from ichnaea import util


class TestCell(CeleryTestCase):

    def test_blacklist_moving_cells(self):
        now = util.utcnow()
        long_ago = now - timedelta(days=40)
        session = self.session

        k1 = dict(radio=Radio.cdma, mcc=1, mnc=2, lac=3, cid=4)
        k2 = dict(radio=Radio.cdma, mcc=1, mnc=2, lac=6, cid=8)
        k3 = dict(radio=Radio.cdma, mcc=1, mnc=2, lac=9, cid=12)
        k4 = dict(radio=Radio.cdma, mcc=1, mnc=2, lac=12, cid=16)
        k5 = dict(radio=Radio.cdma, mcc=1, mnc=2, lac=15, cid=20)
        k6 = dict(radio=Radio.cdma, mcc=1, mnc=2, lac=18, cid=24)

        # keys k2, k3 and k4 are expected to be detected as moving
        data = [
            # a cell with an entry but no prior position
            Cell(new_measures=3, total_measures=0, **k1),
            CellObservation(lat=1.001, lon=1.001, **k1),
            CellObservation(lat=1.002, lon=1.005, **k1),
            CellObservation(lat=1.003, lon=1.009, **k1),
            # a cell with a prior known position
            Cell(lat=2.0, lon=2.0,
                 new_measures=2, total_measures=1, **k2),
            CellObservation(lat=2.0, lon=2.0, **k2),
            CellObservation(lat=4.0, lon=2.0, **k2),
            # a cell with a very different prior position
            Cell(lat=1.0, lon=1.0,
                 new_measures=2, total_measures=1, **k3),
            CellObservation(lat=3.0, lon=3.0, **k3),
            CellObservation(lat=-3.0, lon=3.0, **k3),
            # another cell with a prior known position (and negative lat)
            Cell(lat=-4.0, lon=4.0,
                 new_measures=2, total_measures=1, **k4),
            CellObservation(lat=-4.0, lon=4.0, **k4),
            CellObservation(lat=-6.0, lon=4.0, **k4),
            # an already blacklisted cell
            CellBlacklist(time=now, count=1, **k5),
            CellObservation(lat=5.0, lon=5.0, **k5),
            CellObservation(lat=8.0, lon=5.0, **k5),
            # a cell with an old different record we ignore, position
            # estimate has been updated since
            Cell(lat=6.0, lon=6.0,
                 new_measures=2, total_measures=1, **k6),
            CellObservation(lat=6.9, lon=6.9, time=long_ago, **k6),
            CellObservation(lat=6.0, lon=6.0, **k6),
            CellObservation(lat=6.001, lon=6, **k6),
        ]
        session.add_all(data)
        session.commit()

        result = location_update_cell.delay(min_new=1)
        self.assertEqual(result.get(), (5, 3))

        moving = [k2, k3, k4, k5]
        black = session.query(CellBlacklist).all()
        self.assertEqual(set([b.hashkey() for b in black]),
                         set([CellBlacklist.to_hashkey(k) for k in moving]))

        keys = [k1, k2, k3, k4, k5, k6]
        observations = session.query(CellObservation).all()
        self.assertEqual(len(observations), 14)
        self.assertEqual(set([obs.hashkey() for obs in observations]),
                         set([CellObservation.to_hashkey(k) for k in keys]))

        # test duplicate call
        result = location_update_cell.delay(min_new=1)
        self.assertEqual(result.get(), (0, 0))

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

    def test_blacklist_temporary_and_permanent(self):
        session = self.session

        # This test simulates a cell that moves once a month, for 2 years.
        # The first 2 * PERMANENT_BLACKLIST_THRESHOLD (12) moves should be
        # temporary, forgotten after a week; after that it should be
        # permanently blacklisted.

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

        N = 4 * PERMANENT_BLACKLIST_THRESHOLD
        for month in range(0, N):
            days_ago = (N - (month + 1)) * 30
            time = now - timedelta(days=days_ago)

            obs = dict(radio=int(Radio.gsm),
                       mcc=USA_MCC, mnc=ATT_MNC, lac=456, cid=123,
                       time=time,
                       lat=points[month % 4][0],
                       lon=points[month % 4][1])

            # insert_result is num-accepted-observations, override
            # utcnow to set creation date
            insert_result = insert_measures_cell.delay(
                [obs], utcnow=time)

            # update_result is (num-stations, num-moving-stations)
            update_result = location_update_cell.delay(min_new=1)

            # Assuming PERMANENT_BLACKLIST_THRESHOLD == 6:
            #
            # 0th insert will create the station
            # 1st insert will create first blacklist entry, delete station
            # 2nd insert will recreate the station at new position
            # 3rd insert will update blacklist, re-delete station
            # 4th insert will recreate the station at new position
            # 5th insert will update blacklist, re-delete station
            # 6th insert will recreate the station at new position
            # ...
            # 11th insert will make blacklisting permanent, re-delete station
            # 12th insert will not recreate station
            # 13th insert will not recreate station
            # ...
            # 23rd insert will not recreate station

            bl = session.query(CellBlacklist).all()
            if month == 0:
                self.assertEqual(len(bl), 0)
            else:
                self.assertEqual(len(bl), 1)
                # force the blacklist back in time to whenever the
                # observation was supposedly inserted.
                bl = bl[0]
                bl.time = time
                session.add(bl)
                session.commit()

            if month < N / 2:
                # We still haven't exceeded the threshold, so the
                # observation was admitted.
                self.assertEqual(insert_result.get(), 1)
                self.assertEqual(session.query(CellObservation).count(),
                                 month + 1)
                if month % 2 == 0:
                    # The station was (re)created.
                    self.assertEqual(update_result.get(), (1, 0))
                    # Rescan lacs to update entries
                    self.assertEqual(
                        scan_areas.delay().get(), 1)
                    # One cell + one cell-LAC record should exist.
                    self.assertEqual(session.query(Cell).count(), 1)
                    self.assertEqual(session.query(CellArea).count(), 1)
                else:
                    # The station existed and was seen moving,
                    # thereby activating the blacklist and deleting the cell.
                    self.assertEqual(update_result.get(), (1, 1))
                    # Rescan lacs to delete orphaned lac entry
                    self.assertEqual(
                        scan_areas.delay().get(), 1)
                    self.assertEqual(bl.count, ((month + 1) / 2))
                    self.assertEqual(session.query(CellBlacklist).count(), 1)
                    self.assertEqual(session.query(Cell).count(), 0)

                    # Try adding one more observation 1 day later
                    # to be sure it is dropped by the now-active blacklist.
                    next_day = time + timedelta(days=1)
                    obs['time'] = next_day
                    self.assertEqual(
                        0, insert_measures_cell.delay([obs],
                                                      utcnow=next_day).get())

            else:
                # Blacklist has exceeded threshold, gone to permanent mode,
                # so no observation accepted, no stations seen.
                self.assertEqual(insert_result.get(), 0)
                self.assertEqual(update_result.get(), (0, 0))

    def test_location_update_cell(self):
        now = util.utcnow()
        before = now - timedelta(hours=1)
        obs_factory = CellObservationFactory
        invalid_key = dict(lac=None, cid=None)

        cell1 = CellFactory(new_measures=3, total_measures=5)
        lat1, lon1 = (cell1.lat, cell1.lon)
        key1 = dict(lac=cell1.lac, cid=cell1.cid)
        obs_factory(lat=lat1, lon=lon1, created=now, **key1)
        obs_factory(lat=lat1 + 0.004, lon=lon1 + 0.006, created=now, **key1)
        obs_factory(lat=lat1 + 0.006, lon=lon1 + 0.009, created=now, **key1)
        # The lac, cid are invalid and should be skipped
        obs_factory.create_batch(2, created=now, **invalid_key)

        cell2 = CellFactory(lat=lat1 + 1.0, lon=lon1 + 1.0,
                            new_measures=2, total_measures=4)
        lat2, lon2 = (cell2.lat, cell2.lon)
        key2 = dict(lac=cell2.lac, cid=cell2.cid)
        # the lat/lon is bogus and mismatches the line above on purpose
        # to make sure old observations are skipped
        obs_factory(lat=lat2 - 2.0, lon=lon2 - 2.0, created=before, **key2)
        obs_factory(lat=lat2 - 2.0, lon=lon2 - 2.0, created=before, **key2)
        obs_factory(lat=lat2 + 0.001, lon=lon2 + 0.002, created=now, **key2)
        obs_factory(lat=lat2 + 0.003, lon=lon2 + 0.006, created=now, **key2)

        cell3 = CellFactory(new_measures=10, total_measures=100000)
        lat3, lon3 = (cell3.lat, cell3.lon)
        obs_factory.create_batch(
            10, lat=lat3 + 1.0, lon=lon3 + 1.0,
            **dict(lac=cell3.lac, cid=cell3.cid))
        self.session.commit()

        result = location_update_cell.delay(min_new=1)
        self.assertEqual(result.get(), (3, 0))
        self.check_stats(
            total=2,
            timer=['task.data.location_update_cell'],
            gauge=['task.data.location_update_cell.new_measures_1_100'],
        )

        cells = self.session.query(Cell).all()
        self.assertEqual(len(cells), 3)
        self.assertEqual(set([c.new_measures for c in cells]), set([0]))
        for cell in cells:
            if cell.hashkey() == cell1.hashkey():
                self.assertEqual(cell.lat, lat1 + 0.002)
                self.assertEqual(cell.lon, lon1 + 0.003)
            if cell.hashkey() == cell2.hashkey():
                self.assertEqual(cell.lat, lat2 + 0.001)
                self.assertEqual(cell.lon, lon2 + 0.002)
            if cell.hashkey() == cell3.hashkey():
                expected_lat = ((lat3 * 1000) + (lat3 + 1.0) * 10) / 1010
                expected_lon = ((lon3 * 1000) + (lon3 + 1.0) * 10) / 1010
                self.assertAlmostEqual(cell.lat, expected_lat, 7)
                self.assertAlmostEqual(cell.lon, expected_lon, 7)

    def test_max_min_range_update(self):
        session = self.session

        k1 = dict(radio=Radio.cdma, mcc=1, mnc=2, lac=3, cid=4)
        data = [
            Cell(lat=1.001, lon=-1.001,
                 max_lat=1.002, min_lat=1.0,
                 max_lon=-1.0, min_lon=-1.002,
                 new_measures=2, total_measures=4, **k1),
            CellObservation(lat=1.001, lon=-1.003, **k1),
            CellObservation(lat=1.005, lon=-1.007, **k1),
        ]
        session.add_all(data)
        session.commit()

        result = location_update_cell.delay(min_new=1)
        self.assertEqual(result.get(), (1, 0))

        cells = session.query(Cell).all()
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


class TestWifi(CeleryTestCase):

    def test_blacklist_moving_wifis(self):
        now = util.utcnow()
        long_ago = now - timedelta(days=40)
        session = self.session
        k1 = 'ab1234567890'
        k2 = 'bc1234567890'
        k3 = 'cd1234567890'
        k4 = 'de1234567890'
        k5 = 'ef1234567890'
        k6 = 'fa1234567890'

        keys = set([k1, k2, k3, k4, k5, k6])

        # keys k2, k3 and k4 are expected to be detected as moving
        data = [
            # a wifi with an entry but no prior position
            Wifi(key=k1, new_measures=3, total_measures=0),
            WifiObservation(lat=1.001, lon=1.001, key=k1),
            WifiObservation(lat=1.002, lon=1.005, key=k1),
            WifiObservation(lat=1.003, lon=1.009, key=k1),
            # a wifi with a prior known position
            Wifi(lat=2.0, lon=2.0, key=k2,
                 new_measures=2, total_measures=1),
            WifiObservation(lat=2.01, lon=2, key=k2),
            WifiObservation(lat=2.07, lon=2, key=k2),
            # a wifi with a very different prior position
            Wifi(lat=1.0, lon=1.0, key=k3,
                 new_measures=2, total_measures=1),
            WifiObservation(lat=3.0, lon=3.0, key=k3),
            WifiObservation(lat=-3.0, lon=3.0, key=k3),
            # another wifi with a prior known position (and negative lat)
            Wifi(lat=-4.0, lon=4.0, key=k4,
                 new_measures=2, total_measures=1),
            WifiObservation(lat=-4.1, lon=4, key=k4),
            WifiObservation(lat=-4.16, lon=4, key=k4),
            # an already blacklisted wifi
            WifiBlacklist(key=k5, time=now, count=1),
            WifiObservation(lat=5.0, lon=5.0, key=k5),
            WifiObservation(lat=5.1, lon=5.0, key=k5),
            # a wifi with an old different record we ignore, position
            # estimate has been updated since
            Wifi(lat=6.0, lon=6.0, key=k6,
                 new_measures=2, total_measures=1),
            WifiObservation(lat=6.9, lon=6.9, key=k6, time=long_ago),
            WifiObservation(lat=6.0, lon=6.0, key=k6),
            WifiObservation(lat=6.001, lon=6.0, key=k6),
        ]
        session.add_all(data)
        session.commit()

        result = location_update_wifi.delay(min_new=1)
        self.assertEqual(result.get(), (5, 3))

        black = session.query(WifiBlacklist).all()
        self.assertEqual(set([b.key for b in black]), set([k2, k3, k4, k5]))

        observations = session.query(WifiObservation).all()
        self.assertEqual(len(observations), 14)
        self.assertEqual(set([o.key for o in observations]), keys)

        # test duplicate call
        result = location_update_wifi.delay(min_new=1)
        self.assertEqual(result.get(), (0, 0))

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

    def test_blacklist_temporary_and_permanent(self):
        session = self.session

        # This test simulates a wifi that moves once a month, for 2 years.
        # The first 2 * PERMANENT_BLACKLIST_THRESHOLD (12) moves should be
        # temporary, forgotten after a week; after that it should be
        # permanently blacklisted.

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

        N = 4 * PERMANENT_BLACKLIST_THRESHOLD
        for month in range(0, N):
            days_ago = (N - (month + 1)) * 30
            time = now - timedelta(days=days_ago)

            obs = dict(key='ab1234567890',
                       time=time,
                       lat=points[month % 4][0],
                       lon=points[month % 4][1])

            # insert_result is num-accepted-observations, override
            # utcnow to set creation date
            insert_result = insert_measures_wifi.delay(
                [obs], utcnow=time)

            # update_result is (num-stations, num-moving-stations)
            update_result = location_update_wifi.delay(min_new=1)

            # Assuming PERMANENT_BLACKLIST_THRESHOLD == 6:
            #
            # 0th insert will create the station
            # 1st insert will create first blacklist entry, delete station
            # 2nd insert will recreate the station at new position
            # 3rd insert will update blacklist, re-delete station
            # 4th insert will recreate the station at new position
            # 5th insert will update blacklist, re-delete station
            # 6th insert will recreate the station at new position
            # ...
            # 11th insert will make blacklisting permanent, re-delete station
            # 12th insert will not recreate station
            # 13th insert will not recreate station
            # ...
            # 23rd insert will not recreate station

            bl = session.query(WifiBlacklist).all()
            if month == 0:
                self.assertEqual(len(bl), 0)
            else:
                self.assertEqual(len(bl), 1)
                # force the blacklist back in time to whenever the
                # observation was supposedly inserted.
                bl = bl[0]
                bl.time = time
                session.add(bl)
                session.commit()

            if month < N / 2:
                # We still haven't exceeded the threshold, so the
                # observation was admitted.
                self.assertEqual(insert_result.get(), 1)
                self.assertEqual(session.query(WifiObservation).count(),
                                 month + 1)
                if month % 2 == 0:
                    # The station was (re)created.
                    self.assertEqual(update_result.get(), (1, 0))
                    # One wifi record should exist.
                    self.assertEqual(session.query(Wifi).count(), 1)
                else:
                    # The station existed and was seen moving,
                    # thereby activating the blacklist.
                    self.assertEqual(update_result.get(), (1, 1))
                    self.assertEqual(bl.count, ((month + 1) / 2))
                    self.assertEqual(session.query(WifiBlacklist).count(), 1)
                    self.assertEqual(session.query(Wifi).count(), 0)

                    # Try adding one more observation 1 day later
                    # to be sure it is dropped by the now-active blacklist.
                    next_day = time + timedelta(days=1)
                    obs['time'] = next_day
                    self.assertEqual(
                        0, insert_measures_wifi.delay([obs],
                                                      utcnow=next_day).get())

            else:
                # Blacklist has exceeded threshold, gone to permanent mode,
                # so no observation accepted, no stations seen.
                self.assertEqual(insert_result.get(), 0)
                self.assertEqual(update_result.get(), (0, 0))

    def test_location_update_wifi(self):
        now = util.utcnow()
        before = now - timedelta(days=1)
        session = self.session
        k1 = 'ab1234567890'
        k2 = 'cd1234567890'
        data = [
            Wifi(key=k1, new_measures=3, total_measures=3),
            WifiObservation(lat=1.0, lon=1.0, key=k1, created=now),
            WifiObservation(lat=1.002, lon=1.003, key=k1, created=now),
            WifiObservation(lat=1.004, lon=1.006, key=k1, created=now),
            Wifi(key=k2, lat=2.0, lon=2.0,
                 new_measures=2, total_measures=4),
            # the lat/lon is bogus and mismatches the line above on purpose
            # to make sure old observations are skipped
            WifiObservation(lat=-1.0, lon=-1.0, key=k2, created=before),
            WifiObservation(lat=-1.0, lon=-1.0, key=k2, created=before),
            WifiObservation(lat=2.002, lon=2.004, key=k2, created=now),
            WifiObservation(lat=2.002, lon=2.004, key=k2, created=now),
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
        session = self.session
        k1 = 'ab1234567890'
        k2 = 'cd1234567890'
        data = [
            Wifi(key=k1, new_measures=2, total_measures=2),
            WifiObservation(lat=1.0, lon=1.0, key=k1),
            WifiObservation(lat=1.002, lon=1.004, key=k1),
            Wifi(key=k2, lat=2.0, lon=-2.0,
                 max_lat=2.001, min_lat=1.999,
                 max_lon=-1.999, min_lon=-2.001,
                 new_measures=2, total_measures=4),
            WifiObservation(lat=2.002, lon=-2.004, key=k2),
            WifiObservation(lat=1.998, lon=-1.996, key=k2),
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
        observations = []
        wifi_keys = []
        m1 = 1.0
        m2 = 2.0
        for key in ['a%s1234567890' % i for i in range(5)]:
            wifi = Wifi(key=key)
            wifi_keys.append(wifi.hashkey())
            observations.append(wifi)
            observations.append(WifiObservation(lat=m1, lon=m1, key=key))
            observations.append(WifiObservation(lat=m2, lon=m2, key=key))
        self.session.add_all(observations)
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
