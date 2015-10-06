from collections import defaultdict
from datetime import timedelta

from ichnaea.constants import (
    PERMANENT_BLOCKLIST_THRESHOLD,
    TEMPORARY_BLOCKLIST_DURATION,
)
from ichnaea.data.tasks import (
    update_cell,
    update_cellarea,
    update_wifi,
)
from ichnaea.models import (
    Cell,
    CellArea,
    CellBlocklist,
    StatCounter,
    StatKey,
    WifiShard,
)
from ichnaea.tests.base import CeleryTestCase
from ichnaea.tests.factories import (
    CellFactory,
    CellBlocklistFactory,
    CellObservationFactory,
    WifiShardFactory,
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
            obs_factory(lat=cell.lat + 3.0,
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
        update_cell.delay().get()

        block = self.session.query(CellBlocklist).all()
        self.assertEqual(set([b.hashkey() for b in block]), moving)

        # test duplicate call
        update_cell.delay().get()

        self.check_stats(counter=[
            ('data.station.blocklist', 1, 3,
                ['type:cell', 'action:add', 'reason:moving']),
        ], timer=[
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
                    # Update cell areas
                    update_cellarea.delay().get()
                    # One cell + one cell-LAC record should exist.
                    self.assertEqual(self.session.query(Cell).count(), 1)
                    self.assertEqual(self.session.query(CellArea).count(), 1)
                else:
                    # The station existed and was seen moving,
                    # thereby activating the blocklist and deleting the cell.
                    self.assertEqual(update_cell.delay().get(), (1, 1))
                    # Update cell areas to delete orphaned area entry
                    update_cellarea.delay().get()
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

    def test_max_min_radius_update(self):
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
        self.assertEqual(cell.range, 468)  # BBB
        self.assertEqual(cell.total_measures, 5)  # BBB


class TestWifi(StationTest):

    def _queue_and_update(self, obs):
        sharded_obs = defaultdict(list)
        for ob in obs:
            sharded_obs[WifiShard.shard_id(ob.mac)].append(ob)

        for shard_id, values in sharded_obs.items():
            queue = self.celery_app.data_queues['update_wifi_' + shard_id]
            queue.enqueue(values)
            update_wifi.delay(shard_id=shard_id).get()

    def test_new(self):
        utcnow = util.utcnow()
        obs = WifiObservationFactory.build()
        self._queue_and_update([obs])

        shard = WifiShard.shard_model(obs.mac)
        wifis = self.session.query(shard).all()
        self.assertEqual(len(wifis), 1)
        wifi = wifis[0]
        self.assertAlmostEqual(wifi.lat, obs.lat)
        self.assertAlmostEqual(wifi.max_lat, obs.lat)
        self.assertAlmostEqual(wifi.min_lat, obs.lat)
        self.assertAlmostEqual(wifi.lon, obs.lon)
        self.assertAlmostEqual(wifi.max_lon, obs.lon)
        self.assertAlmostEqual(wifi.min_lon, obs.lon)
        self.assertEqual(wifi.country, 'GB')
        self.assertEqual(wifi.radius, 0)
        self.assertEqual(wifi.samples, 1)
        self.assertEqual(wifi.created.date(), utcnow.date())
        self.assertEqual(wifi.modified.date(), utcnow.date())
        self.assertEqual(wifi.block_first, None)
        self.assertEqual(wifi.block_last, None)
        self.assertEqual(wifi.block_count, None)

    def test_update(self):
        utcnow = util.utcnow()
        obs = []
        obs_factory = WifiObservationFactory
        # first wifi
        wifi1 = WifiShardFactory(lat=None, lon=None, samples=3)
        new_pos = WifiShardFactory.build()
        mac1, lat1, lon1 = (wifi1.mac, new_pos.lat, new_pos.lon)
        obs.extend([
            obs_factory(lat=lat1,
                        lon=lon1, key=mac1),
            obs_factory(lat=lat1 + 0.002,
                        lon=lon1 + 0.003, key=mac1),
            obs_factory(lat=lat1 + 0.004,
                        lon=lon1 + 0.006, key=mac1),
        ])
        # second wifi
        wifi2 = WifiShardFactory(
            lat=lat1 + 1.0, lon=lon1 + 1.0,
            max_lat=lat1 + 1.0, min_lat=lat1 + 0.999,
            max_lon=lon1 + 1.0, min_lon=None,
            radius=20, samples=2,
            created=utcnow - timedelta(10),
            modified=utcnow - timedelta(10))
        mac2, lat2, lon2 = (wifi2.mac, wifi2.lat, wifi2.lon)
        obs.extend([
            obs_factory(lat=lat2 + 0.002,
                        lon=lon2 + 0.004, key=mac2),
            obs_factory(lat=lat2 + 0.002,
                        lon=lon2 + 0.004, key=mac2),
        ])
        self.session.commit()
        self._queue_and_update(obs)

        shard = WifiShard.shard_model(mac1)
        found = self.session.query(shard).filter(shard.mac == mac1).one()
        self.assertAlmostEqual(found.lat, lat1 + 0.002)
        self.assertAlmostEqual(found.max_lat, lat1 + 0.004)
        self.assertAlmostEqual(found.min_lat, lat1)
        self.assertAlmostEqual(found.lon, lon1 + 0.003)
        self.assertAlmostEqual(found.max_lon, lon1 + 0.006)
        self.assertAlmostEqual(found.min_lon, lon1)
        self.assertEqual(found.modified.date(), utcnow.date())
        self.assertEqual(found.country, 'GB')
        self.assertEqual(found.radius, 304)
        self.assertEqual(found.samples, 6)

        shard = WifiShard.shard_model(mac2)
        found = self.session.query(shard).filter(shard.mac == mac2).one()
        self.assertAlmostEqual(found.lat, lat2 + 0.001)
        self.assertAlmostEqual(found.max_lat, lat2 + 0.002)
        self.assertAlmostEqual(found.min_lat, lat2 - 0.001)
        self.assertAlmostEqual(found.lon, lon2 + 0.002)
        self.assertAlmostEqual(found.max_lon, lon2 + 0.004)
        self.assertAlmostEqual(found.min_lon, lon2)
        self.assertEqual(found.created.date(), utcnow.date() - timedelta(10))
        self.assertEqual(found.modified.date(), utcnow.date())
        self.assertEqual(found.country, 'GB')
        self.assertEqual(found.radius, 260)
        self.assertEqual(found.samples, 4)

    def test_temp_blocked(self):
        utcnow = util.utcnow()
        bad_wifi = WifiObservationFactory.build()
        good_wifi = WifiObservationFactory.build()
        WifiShardFactory(
            mac=bad_wifi.mac,
            lat=None,
            lon=None,
            created=utcnow,
            block_first=utcnow.date() - timedelta(days=10),
            block_last=utcnow.date(),
            block_count=1)
        obs = [good_wifi, bad_wifi, good_wifi]
        self.session.commit()
        self._queue_and_update(obs)

        shard = WifiShard.shard_model(good_wifi.mac)
        wifis = (self.session.query(shard)
                             .filter(shard.mac == good_wifi.mac)).all()
        self.assertEqual(len(wifis), 1)
        self.assertTrue(wifis[0].lat is not None)
        self.assertTrue(wifis[0].lon is not None)
        self.assertEqual(wifis[0].samples, 2)

        shard = WifiShard.shard_model(bad_wifi.mac)
        wifis = (self.session.query(shard)
                             .filter(shard.mac == bad_wifi.mac)).all()
        self.assertEqual(len(wifis), 1)
        self.assertTrue(wifis[0].lat is None)
        self.assertTrue(wifis[0].lon is None)

        self.check_statcounter(StatKey.wifi, 2)
        self.check_statcounter(StatKey.unique_wifi, 1)

    def test_temp_blocked_admitted_again(self):
        now = util.utcnow()
        last_week = now - TEMPORARY_BLOCKLIST_DURATION - timedelta(days=1)

        obs = WifiObservationFactory()
        WifiShardFactory(
            mac=obs.mac,
            lat=None,
            lon=None,
            samples=0,
            created=last_week,
            modified=last_week,
            block_first=last_week.date(),
            block_last=last_week.date(),
            block_count=1)
        self.session.commit()
        # add a new entry for the previously blocked wifi
        self._queue_and_update([obs])

        # the wifi was inserted again
        shard = WifiShard.shard_model(obs.mac)
        wifis = self.session.query(shard).all()
        self.assertEqual(len(wifis), 1)
        wifi = wifis[0]
        self.assertEqual(wifi.created.date(), last_week.date())
        self.assertAlmostEqual(wifi.lat, obs.lat)
        self.assertAlmostEqual(wifi.lon, obs.lon)
        self.assertEqual(wifi.country, 'GB')
        self.assertEqual(wifi.samples, 1)
        self.check_statcounter(StatKey.unique_wifi, 0)

    def test_blocklist_moving_wifis(self):
        now = util.utcnow()
        obs = []
        obs_factory = WifiObservationFactory
        moving = set()
        wifis = WifiShardFactory.create_batch(7)
        wifis.append(WifiShardFactory.build())
        # a wifi without an entry and disagreeing observations
        wifi = wifis[-1]
        obs.extend([
            obs_factory(lat=wifi.lat, lon=wifi.lon, key=wifi.mac),
            obs_factory(lat=wifi.lat + 2.0, lon=wifi.lon, key=wifi.mac),
        ])
        moving.add(wifi.mac)
        # a wifi with an entry but no prior position
        wifi = wifis[0]
        obs.extend([
            obs_factory(lat=wifi.lat + 0.001,
                        lon=wifi.lon + 0.001, key=wifi.mac),
            obs_factory(lat=wifi.lat + 0.002,
                        lon=wifi.lon + 0.005, key=wifi.mac),
            obs_factory(lat=wifi.lat + 0.003,
                        lon=wifi.lon + 0.009, key=wifi.mac),
        ])
        wifi.lat = None
        wifi.lon = None
        wifi.samples = 0
        # a wifi with a prior known position
        wifi = wifis[1]
        wifi.samples = 1
        wifi.lat += 1.0
        wifi.lon += 1.0
        obs.extend([
            obs_factory(lat=wifi.lat + 0.01,
                        lon=wifi.lon, key=wifi.mac),
            obs_factory(lat=wifi.lat + 0.07,
                        lon=wifi.lon, key=wifi.mac),
        ])
        moving.add(wifi.mac)
        # a wifi with a very different prior position
        wifi = wifis[2]
        wifi.samples = 1
        obs.extend([
            obs_factory(lat=wifi.lat + 2.0,
                        lon=wifi.lon, key=wifi.mac),
            obs_factory(lat=wifi.lat + 2.002,
                        lon=wifi.lon, key=wifi.mac),
        ])
        moving.add(wifi.mac)
        # an already blocked wifi
        wifi = wifis[3]
        wifi.block_last = now.date()
        wifi.block_count = 1
        obs.extend([
            obs_factory(lat=wifi.lat,
                        lon=wifi.lon, key=wifi.mac),
            obs_factory(lat=wifi.lat + 0.1,
                        lon=wifi.lon, key=wifi.mac),
        ])
        moving.add(wifi.mac)
        # a permanently blocked wifi
        wifi = wifis[4]
        wifi_lat, wifi_lon = (wifi.lat, wifi.lon)
        wifi.block_last = now.date() - 2 * TEMPORARY_BLOCKLIST_DURATION
        wifi.block_count = PERMANENT_BLOCKLIST_THRESHOLD
        for col in ('lat', 'lon', 'max_lat', 'min_lat', 'max_lon', 'min_lon'):
            setattr(wifi, col, None)
        obs.extend([
            obs_factory(lat=wifi_lat, lon=wifi_lon, key=wifi.mac),
        ])
        moving.add(wifi.mac)
        # a no longer blocked wifi
        wifi = wifis[5]
        wifi_lat, wifi_lon = (wifi.lat, wifi.lon)
        wifi.block_last = now.date() - 2 * TEMPORARY_BLOCKLIST_DURATION
        wifi.block_count = 2
        for col in ('lat', 'lon', 'max_lat', 'min_lat', 'max_lon', 'min_lon'):
            setattr(wifi, col, None)
        obs.extend([
            obs_factory(lat=wifi_lat, lon=wifi_lon, key=wifi.mac),
        ])
        # a no longer blocked wifi with disagreeing observations
        wifi = wifis[6]
        wifi_lat, wifi_lon = (wifi.lat, wifi.lon)
        wifi.block_last = now.date() - 2 * TEMPORARY_BLOCKLIST_DURATION
        wifi.block_count = 2
        for col in ('lat', 'lon', 'max_lat', 'min_lat', 'max_lon', 'min_lon'):
            setattr(wifi, col, None)
        obs.extend([
            obs_factory(lat=wifi_lat, lon=wifi_lon, key=wifi.mac),
            obs_factory(lat=wifi_lat + 2.0, lon=wifi_lon, key=wifi.mac),
        ])
        moving.add(wifi.mac)
        self.session.commit()
        self._queue_and_update(obs)

        shards = set()
        for mac in moving:
            shards.add(WifiShard.shard_model(mac))
        blocks = []
        for shard in shards:
            for row in self.session.query(shard).all():
                if row.blocked():
                    blocks.append(row)
        self.assertEqual(set([b.mac for b in blocks]), moving)

    def test_country(self):
        obs = []
        obs_factory = WifiObservationFactory
        wifi1 = WifiShardFactory(lat=46.2884, lon=6.77, country='FR')
        obs.extend(obs_factory.create_batch(
            5, key=wifi1.mac, lat=wifi1.lat, lon=wifi1.lon + 0.05,
        ))
        wifi2 = WifiShardFactory(lat=46.2884, lon=7.4, country='FR')
        obs.extend(obs_factory.create_batch(
            5, key=wifi2.mac, lat=wifi2.lat, lon=wifi2.lon + 0.05,
        ))
        self.session.commit()
        self._queue_and_update(obs)

        # position is really not in FR anymore, but still close enough
        # to not re-trigger region determination
        wifi1 = self.session.query(wifi1.__class__).get(wifi1.mac)
        self.assertEqual(wifi1.block_count, 0)
        self.assertEqual(wifi1.country, 'FR')
        wifi2 = self.session.query(wifi2.__class__).get(wifi2.mac)
        self.assertEqual(wifi1.block_count, 0)
        self.assertEqual(wifi2.country, 'CH')
