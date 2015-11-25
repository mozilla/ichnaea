from collections import defaultdict
from datetime import timedelta

from ichnaea.constants import (
    PERMANENT_BLOCKLIST_THRESHOLD,
    TEMPORARY_BLOCKLIST_DURATION,
)
from ichnaea.data.tasks import (
    update_cell,
    update_wifi,
)
from ichnaea.models import (
    CellShard,
    StatCounter,
    StatKey,
    WifiShard,
)
from ichnaea.tests.base import CeleryTestCase
from ichnaea.tests.factories import (
    CellObservationFactory,
    CellShardFactory,
    WifiObservationFactory,
    WifiShardFactory,
)
from ichnaea import util


class StationTest(CeleryTestCase):

    def _compare_sets(self, one, two):
        self.assertEqual(set(one), set(two))

    def check_statcounter(self, stat_key, value):
        stat_counter = StatCounter(stat_key, util.utcnow())
        self.assertEqual(stat_counter.get(self.redis_client), value)


class TestCell(StationTest):

    def _queue_and_update(self, obs):
        sharded_obs = defaultdict(list)
        for ob in obs:
            sharded_obs[CellShard.shard_id(ob.cellid)].append(ob)

        for shard_id, values in sharded_obs.items():
            queue = self.celery_app.data_queues['update_cell_' + shard_id]
            queue.enqueue(values)
            update_cell.delay(shard_id=shard_id).get()

    def test_shard_queues(self):  # BBB
        observations = CellObservationFactory.build_batch(3)
        data_queues = self.celery_app.data_queues
        single_queue = data_queues['update_cell']
        single_queue.enqueue(observations)
        update_cell.delay().get()

        self.assertEqual(single_queue.size(), 0)

        total = 0
        for shard_id in CellShard.shards().keys():
            total += data_queues['update_cell_' + shard_id].size()

        self.assertEqual(total, 3)

    def test_blocklist(self):
        now = util.utcnow()
        today = now.date()
        observations = CellObservationFactory.build_batch(3)
        obs = observations[0]
        CellShardFactory(
            radio=obs.radio, mcc=obs.mcc, mnc=obs.mnc,
            lac=obs.lac, cid=obs.cid,
            created=now,
            block_first=today - timedelta(days=10),
            block_last=today,
            block_count=1,
        )
        self.session.commit()
        self._queue_and_update(observations)

        blocks = []
        for obs in observations:
            shard = CellShard.shard_model(obs.cellid)
            cell = (self.session.query(shard)
                                .filter(shard.cellid == obs.cellid)).one()
            if cell.blocked():
                blocks.append(cell)

        self.assertEqual(len(blocks), 1)
        self.check_statcounter(StatKey.cell, 2)
        self.check_statcounter(StatKey.unique_cell, 2)

    def test_blocklist_moving_cells(self):
        now = util.utcnow()
        today = now.date()
        obs = []
        obs_factory = CellObservationFactory
        moving = set()
        cells = CellShardFactory.create_batch(4)
        cells.append(CellShardFactory.build())
        # a cell with an entry but no prior position
        cell = cells[0]
        cell_key = dict(radio=cell.radio, mcc=cell.mcc, mnc=cell.mnc,
                        lac=cell.lac, cid=cell.cid)
        cell.samples = 0
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
        cell_key = dict(radio=cell.radio, mcc=cell.mcc, mnc=cell.mnc,
                        lac=cell.lac, cid=cell.cid)
        cell.samples = 1
        cell.lat += 0.1
        obs.extend([
            obs_factory(lat=cell.lat + 1.0,
                        lon=cell.lon, **cell_key),
            obs_factory(lat=cell.lat + 3.0,
                        lon=cell.lon, **cell_key),
        ])
        moving.add(cell.cellid)
        # a cell with a very different prior position
        cell = cells[2]
        cell_key = dict(radio=cell.radio, mcc=cell.mcc, mnc=cell.mnc,
                        lac=cell.lac, cid=cell.cid)
        cell.samples = 1
        obs.extend([
            obs_factory(lat=cell.lat + 3.0,
                        lon=cell.lon, **cell_key),
            obs_factory(lat=cell.lat - 0.1,
                        lon=cell.lon, **cell_key),
        ])
        moving.add(cell.cellid)
        # another cell with a prior known position (and negative lon)
        cell = cells[3]
        cell_key = dict(radio=cell.radio, mcc=cell.mcc, mnc=cell.mnc,
                        lac=cell.lac, cid=cell.cid)
        cell.samples = 1
        cell.lon *= -1.0
        obs.extend([
            obs_factory(lat=cell.lat + 1.0,
                        lon=cell.lon, **cell_key),
            obs_factory(lat=cell.lat + 2.0,
                        lon=cell.lon, **cell_key),
        ])
        moving.add(cell.cellid)
        # an already blocklisted cell
        cell = cells[4]
        cell_key = dict(radio=cell.radio, mcc=cell.mcc, mnc=cell.mnc,
                        lac=cell.lac, cid=cell.cid)
        CellShardFactory(block_first=today, block_last=today, block_count=1,
                         **cell_key)
        obs.extend([
            obs_factory(lat=cell.lat,
                        lon=cell.lon, **cell_key),
            obs_factory(lat=cell.lat + 3.0,
                        lon=cell.lon, **cell_key),
        ])
        moving.add(cell.cellid)
        self.session.commit()
        self._queue_and_update(obs)

        shards = set()
        for cellid in moving:
            shards.add(CellShard.shard_model(cellid))
        blocks = []
        for shard in shards:
            for row in self.session.query(shard).all():
                if row.blocked():
                    blocks.append(row)
        self.assertEqual(set([b.cellid for b in blocks]), moving)

    def test_update(self):
        now = util.utcnow()
        invalid_key = dict(lac=None, cid=None)
        observations = []

        def obs_factory(**kw):
            obs = CellObservationFactory.build(**kw)
            if obs is not None:
                observations.append(obs)

        cell1 = CellShardFactory(samples=3)
        lat1, lon1 = (cell1.lat, cell1.lon)
        key1 = dict(radio=cell1.radio, lac=cell1.lac, cid=cell1.cid)
        obs_factory(lat=lat1, lon=lon1, created=now, **key1)
        obs_factory(lat=lat1 + 0.004, lon=lon1 + 0.006, created=now, **key1)
        obs_factory(lat=lat1 + 0.006, lon=lon1 + 0.009, created=now, **key1)
        # The lac, cid are invalid and should be skipped
        obs_factory(created=now, **invalid_key)
        obs_factory(created=now, **invalid_key)

        cell2 = CellShardFactory(lat=lat1 + 1.0, lon=lon1 + 1.0, samples=3)
        lat2, lon2 = (cell2.lat, cell2.lon)
        key2 = dict(radio=cell2.radio, lac=cell2.lac, cid=cell2.cid)
        obs_factory(lat=lat2 + 0.001, lon=lon2 + 0.002, created=now, **key2)
        obs_factory(lat=lat2 + 0.003, lon=lon2 + 0.006, created=now, **key2)

        cell3 = CellShardFactory(samples=100000)
        lat3, lon3 = (cell3.lat, cell3.lon)
        key3 = dict(radio=cell3.radio, lac=cell3.lac, cid=cell3.cid)
        for i in range(10):
            obs_factory(lat=lat3 + 1.0, lon=lon3 + 1.0, **key3)

        self.session.commit()
        self._queue_and_update(observations)

        shard = CellShard.shard_model(cell1.cellid)
        found = (self.session.query(shard)
                             .filter(shard.cellid == cell1.cellid)).one()
        self.assertAlmostEqual(found.lat, lat1 + 0.001667, 6)
        self.assertAlmostEqual(found.lon, lon1 + 0.0025, 6)

        shard = CellShard.shard_model(cell2.cellid)
        found = (self.session.query(shard)
                             .filter(shard.cellid == cell2.cellid)).one()
        self.assertAlmostEqual(found.lat, lat2 + 0.0008, 6)
        self.assertAlmostEqual(found.lon, lon2 + 0.0016, 6)

        shard = CellShard.shard_model(cell3.cellid)
        found = (self.session.query(shard)
                             .filter(shard.cellid == cell3.cellid)).one()
        expected_lat = ((lat3 * 1000) + (lat3 + 1.0) * 10) / 1010
        expected_lon = ((lon3 * 1000) + (lon3 + 1.0) * 10) / 1010
        self.assertAlmostEqual(found.lat, expected_lat, 7)
        self.assertAlmostEqual(found.lon, expected_lon, 7)

    def test_max_min_radius_update(self):
        cell = CellShardFactory(radius=150, samples=3)
        cell_lat = cell.lat
        cell_lon = cell.lon
        cell.max_lat = cell.lat + 0.001
        cell.min_lat = cell.lat - 0.001
        cell.max_lon = cell.lon + 0.001
        cell.min_lon = cell.lon - 0.001
        k1 = dict(radio=cell.radio, mcc=cell.mcc, mnc=cell.mnc,
                  lac=cell.lac, cid=cell.cid)

        obs_factory = CellObservationFactory
        obs = [
            obs_factory(lat=cell.lat, lon=cell.lon - 0.002, **k1),
            obs_factory(lat=cell.lat + 0.004, lon=cell.lon - 0.006, **k1),
        ]

        self.session.commit()
        self._queue_and_update(obs)

        shard = CellShard.shard_model(cell.cellid)
        cells = self.session.query(shard).all()
        self.assertEqual(len(cells), 1)
        cell = cells[0]
        self.assertAlmostEqual(cell.lat, cell_lat + 0.0008)
        self.assertAlmostEqual(cell.max_lat, cell_lat + 0.004)
        self.assertAlmostEqual(cell.min_lat, cell_lat - 0.001)
        self.assertAlmostEqual(cell.lon, cell_lon - 0.0016)
        self.assertAlmostEqual(cell.max_lon, cell_lon + 0.001)
        self.assertAlmostEqual(cell.min_lon, cell_lon - 0.006)
        self.assertEqual(cell.radius, 468)
        self.assertEqual(cell.samples, 5)


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
        self.assertEqual(wifi.radius, 0)
        self.assertEqual(wifi.region, 'GB')
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
        self.assertEqual(found.radius, 304)
        self.assertEqual(found.region, 'GB')
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
        self.assertEqual(found.radius, 260)
        self.assertEqual(found.region, 'GB')
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
        self.assertTrue(wifis[0].block_first < utcnow.date())
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
        self.assertEqual(wifi.block_first, last_week.date())
        self.assertEqual(wifi.block_last, last_week.date())
        self.assertEqual(wifi.created.date(), last_week.date())
        self.assertAlmostEqual(wifi.lat, obs.lat)
        self.assertAlmostEqual(wifi.lon, obs.lon)
        self.assertEqual(wifi.region, 'GB')
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

    def test_region(self):
        obs = []
        obs_factory = WifiObservationFactory
        wifi1 = WifiShardFactory(lat=46.2884, lon=6.77, region='FR')
        obs.extend(obs_factory.create_batch(
            5, key=wifi1.mac, lat=wifi1.lat, lon=wifi1.lon + 0.05,
        ))
        wifi2 = WifiShardFactory(lat=46.2884, lon=7.4, region='FR')
        obs.extend(obs_factory.create_batch(
            5, key=wifi2.mac, lat=wifi2.lat, lon=wifi2.lon + 0.05,
        ))
        self.session.commit()
        self._queue_and_update(obs)

        # position is really not in FR anymore, but still close enough
        # to not re-trigger region determination
        wifi1 = self.session.query(wifi1.__class__).get(wifi1.mac)
        self.assertEqual(wifi1.block_count, 0)
        self.assertEqual(wifi1.region, 'FR')
        wifi2 = self.session.query(wifi2.__class__).get(wifi2.mac)
        self.assertEqual(wifi1.block_count, 0)
        self.assertEqual(wifi2.region, 'CH')
