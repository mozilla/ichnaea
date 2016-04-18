from collections import defaultdict
from datetime import timedelta

import mock
from sqlalchemy import text

from ichnaea.data.station import CellUpdater
from ichnaea.data.tasks import (
    update_blue,
    update_cell,
    update_wifi,
)
from ichnaea.models import (
    BlueShard,
    CellShard,
    Radio,
    ReportSource,
    StatCounter,
    StatKey,
    WifiShard,
)
from ichnaea.models.constants import TEMPORARY_BLOCKLIST_DURATION
from ichnaea.tests.base import CeleryTestCase
from ichnaea.tests.factories import (
    BlueObservationFactory,
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

    def _queue_and_update_blue(self, obs):
        sharded_obs = defaultdict(list)
        for ob in obs:
            sharded_obs[BlueShard.shard_id(ob.mac)].append(ob)

        for shard_id, values in sharded_obs.items():
            queue = self.celery_app.data_queues['update_blue_' + shard_id]
            queue.enqueue([value.to_json() for value in values])
            update_blue.delay(shard_id=shard_id).get()

    def _queue_and_update_cell(self, obs):
        sharded_obs = defaultdict(list)
        for ob in obs:
            sharded_obs[CellShard.shard_id(ob.cellid)].append(ob)

        for shard_id, values in sharded_obs.items():
            queue = self.celery_app.data_queues['update_cell_' + shard_id]
            queue.enqueue([value.to_json() for value in values])
            update_cell.delay(shard_id=shard_id).get()

    def _queue_and_update_wifi(self, obs):
        sharded_obs = defaultdict(list)
        for ob in obs:
            sharded_obs[WifiShard.shard_id(ob.mac)].append(ob)

        for shard_id, values in sharded_obs.items():
            queue = self.celery_app.data_queues['update_wifi_' + shard_id]
            queue.enqueue([value.to_json() for value in values])
            update_wifi.delay(shard_id=shard_id).get()


class TestDatabaseErrors(StationTest):
    # this is a standalone class to ensure DB isolation

    def tearDown(self):
        for model in CellShard.shards().values():
            self.session.execute(text('drop table %s;' % model.__tablename__))

        self.setup_tables(self.db_rw.engine)
        super(TestDatabaseErrors, self).tearDown()

    def test_lock_timeout(self):
        obs = CellObservationFactory.build()
        cell = CellShardFactory.build(
            radio=obs.radio, mcc=obs.mcc, mnc=obs.mnc,
            lac=obs.lac, cid=obs.cid,
            samples=10,
        )
        self.db_ro_session.add(cell)
        self.db_ro_session.flush()

        orig_add_area = CellUpdater.add_area_update
        orig_wait = CellUpdater._retry_wait
        num = [0]

        def mock_area(self, updated_areas, key,
                      num=num, ro_session=self.db_ro_session):
            orig_add_area(self, updated_areas, key)
            num[0] += 1
            if num[0] == 2:
                ro_session.rollback()

        try:
            CellUpdater._retry_wait = 0.001
            self.session.execute('set session innodb_lock_wait_timeout = 1')
            with mock.patch.object(CellUpdater, 'add_area_update', mock_area):
                self._queue_and_update_cell([obs])
        finally:
            CellUpdater._retry_wait = orig_wait

        # the inner task logic was called exactly twice
        self.assertEqual(num[0], 2)

        shard = CellShard.shard_model(obs.cellid)
        cells = self.session.query(shard).all()
        self.assertEqual(len(cells), 1)
        self.assertEqual(cells[0].samples, 1)

        self.check_statcounter(StatKey.cell, 1)
        self.check_statcounter(StatKey.unique_cell, 1)
        self.check_stats(
            counter=[('data.observation.insert', 1, ['type:cell'])],
            timer=[('task', 1, ['task:data.update_cell'])],
        )


class TestBlue(StationTest):

    def test_new(self):
        utcnow = util.utcnow()
        obs = BlueObservationFactory.build()
        self._queue_and_update_blue([obs])

        shard = BlueShard.shard_model(obs.mac)
        blues = self.session.query(shard).all()
        self.assertEqual(len(blues), 1)
        blue = blues[0]
        self.assertAlmostEqual(blue.lat, obs.lat)
        self.assertAlmostEqual(blue.max_lat, obs.lat)
        self.assertAlmostEqual(blue.min_lat, obs.lat)
        self.assertAlmostEqual(blue.lon, obs.lon)
        self.assertAlmostEqual(blue.max_lon, obs.lon)
        self.assertAlmostEqual(blue.min_lon, obs.lon)
        self.assertEqual(blue.radius, 0)
        self.assertEqual(blue.region, 'GB')
        self.assertEqual(blue.samples, 1)
        self.assertAlmostEqual(blue.weight, 1.0, 2)
        self.assertEqual(blue.created.date(), utcnow.date())
        self.assertEqual(blue.modified.date(), utcnow.date())
        self.assertEqual(blue.block_first, None)
        self.assertEqual(blue.block_last, None)
        self.assertEqual(blue.block_count, None)

    def test_query(self):
        obs = BlueObservationFactory.build(source=ReportSource.query)
        self._queue_and_update_blue([obs])
        shard = BlueShard.shard_model(obs.mac)
        blues = self.session.query(shard).all()
        self.assertEqual(len(blues), 0)


class TestCell(StationTest):

    def test_query(self):
        obs = CellObservationFactory.build(source=ReportSource.query)
        self._queue_and_update_cell([obs])
        shard = CellShard.shard_model(obs.cellid)
        cells = self.session.query(shard).all()
        self.assertEqual(len(cells), 0)

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
        self._queue_and_update_cell(observations)

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
        cell.samples = None
        cell.weight = None
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
        cell.weight = 1.0
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
        cell.weight = 1.0
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
        cell.weight = 1.0
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
        self._queue_and_update_cell(obs)

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

        cell1 = CellShardFactory(samples=3, weight=3.0)
        lat1, lon1 = (cell1.lat, cell1.lon)
        key1 = dict(radio=cell1.radio, lac=cell1.lac, cid=cell1.cid)
        obs_factory(lat=lat1, lon=lon1, created=now, **key1)
        obs_factory(lat=lat1 + 0.004, lon=lon1 + 0.006, created=now, **key1)
        obs_factory(lat=lat1 + 0.006, lon=lon1 + 0.009, created=now, **key1)
        # The lac, cid are invalid and should be skipped
        obs_factory(created=now, **invalid_key)
        obs_factory(created=now, **invalid_key)

        cell2 = CellShardFactory(
            lat=lat1 + 1.0, lon=lon1 + 1.0, samples=3, weight=3.0)
        lat2, lon2 = (cell2.lat, cell2.lon)
        key2 = dict(radio=cell2.radio, lac=cell2.lac, cid=cell2.cid)
        obs_factory(lat=lat2 + 0.001, lon=lon2 + 0.002, created=now, **key2)
        obs_factory(lat=lat2 + 0.003, lon=lon2 + 0.006, created=now, **key2)

        cell3 = CellShardFactory(samples=100000, weight=100000.0)
        lat3, lon3 = (cell3.lat, cell3.lon)
        key3 = dict(radio=cell3.radio, lac=cell3.lac, cid=cell3.cid)
        for i in range(10):
            obs_factory(lat=lat3 + 0.5, lon=lon3 + 0.5, **key3)

        self.session.commit()
        self._queue_and_update_cell(observations)

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
        expected_lat = ((lat3 * 10000) + (lat3 + 0.5) * 10) / 10010
        expected_lon = ((lon3 * 10000) + (lon3 + 0.5) * 10) / 10010
        self.assertAlmostEqual(found.lat, expected_lat, 7)
        self.assertAlmostEqual(found.lon, expected_lon, 7)

    def test_max_min_radius_update(self):
        cell = CellShardFactory(radius=150, samples=3, weight=3.0)
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
        self._queue_and_update_cell(obs)

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
        self.assertEqual(cell.radius, 469)
        self.assertEqual(cell.samples, 5)
        self.assertAlmostEqual(cell.weight, 5.0, 2)

    def test_weighted_update(self):
        cell = CellShardFactory(radio=Radio.gsm, samples=1, weight=2.0)
        cell_lat = cell.lat
        cell_lon = cell.lon
        cell_key = dict(radio=cell.radio, mcc=cell.mcc, mnc=cell.mnc,
                        lac=cell.lac, cid=cell.cid)

        obs_factory = CellObservationFactory
        obs = [
            obs_factory(lat=cell.lat, lon=cell.lon - 0.002,
                        accuracy=20.0, signal=-51, **cell_key),
            obs_factory(lat=cell.lat, signal=-111, lon=cell.lon - 0.004,
                        accuracy=40.0, **cell_key),
        ]

        self.session.commit()
        self._queue_and_update_cell(obs)
        shard = CellShard.shard_model(cell.cellid)
        cells = self.session.query(shard).all()
        self.assertEqual(len(cells), 1)
        cell = cells[0]
        self.assertAlmostEqual(cell.lat, cell_lat)
        self.assertAlmostEqual(cell.max_lat, cell_lat)
        self.assertAlmostEqual(cell.min_lat, cell_lat)
        self.assertAlmostEqual(cell.lon, cell_lon - 0.0016358, 7)
        self.assertAlmostEqual(cell.max_lon, cell_lon)
        self.assertAlmostEqual(cell.min_lon, cell_lon - 0.004)
        self.assertEqual(cell.radius, 164)
        self.assertEqual(cell.samples, 3)
        self.assertAlmostEqual(cell.weight, 9.47, 2)


class TestWifi(StationTest):

    def test_new(self):
        utcnow = util.utcnow()
        obs = WifiObservationFactory.build()
        self._queue_and_update_wifi([obs])

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
        self.assertAlmostEqual(wifi.weight, 1.0, 2)
        self.assertEqual(wifi.created.date(), utcnow.date())
        self.assertEqual(wifi.modified.date(), utcnow.date())
        self.assertEqual(wifi.block_first, None)
        self.assertEqual(wifi.block_last, None)
        self.assertEqual(wifi.block_count, None)

    def test_query(self):
        obs = WifiObservationFactory.build(source=ReportSource.query)
        self._queue_and_update_wifi([obs])
        shard = WifiShard.shard_model(obs.mac)
        wifis = self.session.query(shard).all()
        self.assertEqual(len(wifis), 0)

    def test_update(self):
        utcnow = util.utcnow()
        obs = []
        obs_factory = WifiObservationFactory
        # first wifi
        wifi1 = WifiShardFactory(lat=None, lon=None, samples=3, weight=3.0)
        new_pos = WifiShardFactory.build()
        mac1, lat1, lon1 = (wifi1.mac, new_pos.lat, new_pos.lon)
        obs.extend([
            obs_factory(lat=lat1,
                        lon=lon1, mac=mac1),
            obs_factory(lat=lat1 + 0.002,
                        lon=lon1 + 0.003, mac=mac1),
            obs_factory(lat=lat1 + 0.004,
                        lon=lon1 + 0.006, mac=mac1),
        ])
        # second wifi
        wifi2 = WifiShardFactory(
            lat=lat1 + 1.0, lon=lon1 + 1.0,
            max_lat=lat1 + 1.0, min_lat=lat1 + 0.999,
            max_lon=lon1 + 1.0, min_lon=None,
            radius=20, samples=2, weight=2.0,
            created=utcnow - timedelta(10),
            modified=utcnow - timedelta(10))
        mac2, lat2, lon2 = (wifi2.mac, wifi2.lat, wifi2.lon)
        obs.extend([
            obs_factory(lat=lat2 + 0.002,
                        lon=lon2 + 0.004, mac=mac2),
            obs_factory(lat=lat2 + 0.002,
                        lon=lon2 + 0.004, mac=mac2),
        ])
        self.session.commit()
        self._queue_and_update_wifi(obs)

        shard = WifiShard.shard_model(mac1)
        found = self.session.query(shard).filter(shard.mac == mac1).one()
        self.assertAlmostEqual(found.lat, lat1 + 0.002)
        self.assertAlmostEqual(found.max_lat, lat1 + 0.004)
        self.assertAlmostEqual(found.min_lat, lat1)
        self.assertAlmostEqual(found.lon, lon1 + 0.003)
        self.assertAlmostEqual(found.max_lon, lon1 + 0.006)
        self.assertAlmostEqual(found.min_lon, lon1)
        self.assertEqual(found.modified.date(), utcnow.date())
        self.assertEqual(found.radius, 305)
        self.assertEqual(found.region, 'GB')
        self.assertEqual(found.samples, 6)
        self.assertAlmostEqual(found.weight, 6.0, 2)

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
        self.assertEqual(found.radius, 261)
        self.assertEqual(found.region, 'GB')
        self.assertEqual(found.samples, 4)
        self.assertAlmostEqual(found.weight, 4.0, 2)

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
        self._queue_and_update_wifi(obs)

        shard = WifiShard.shard_model(good_wifi.mac)
        wifis = (self.session.query(shard)
                             .filter(shard.mac == good_wifi.mac)).all()
        self.assertEqual(len(wifis), 1)
        self.assertTrue(wifis[0].lat is not None)
        self.assertTrue(wifis[0].lon is not None)
        self.assertEqual(wifis[0].samples, 2)
        self.assertAlmostEqual(wifis[0].weight, 2.0, 2)

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
        two_months = now - timedelta(days=46)

        obs = WifiObservationFactory()
        WifiShardFactory(
            mac=obs.mac,
            lat=None,
            lon=None,
            samples=None,
            weight=None,
            created=two_months,
            modified=last_week,
            block_first=last_week.date(),
            block_last=last_week.date(),
            block_count=1)
        self.session.commit()
        # add a new entry for the previously blocked wifi
        self._queue_and_update_wifi([obs])

        # the wifi was inserted again
        shard = WifiShard.shard_model(obs.mac)
        wifis = self.session.query(shard).all()
        self.assertEqual(len(wifis), 1)
        wifi = wifis[0]
        self.assertEqual(wifi.block_first, last_week.date())
        self.assertEqual(wifi.block_last, last_week.date())
        self.assertEqual(wifi.created.date(), two_months.date())
        self.assertAlmostEqual(wifi.lat, obs.lat)
        self.assertAlmostEqual(wifi.lon, obs.lon)
        self.assertEqual(wifi.region, 'GB')
        self.assertEqual(wifi.samples, 1)
        self.assertAlmostEqual(wifi.weight, 1.0, 2)
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
            obs_factory(lat=wifi.lat, lon=wifi.lon, mac=wifi.mac),
            obs_factory(lat=wifi.lat + 2.0, lon=wifi.lon, mac=wifi.mac),
        ])
        moving.add(wifi.mac)
        # a wifi with an entry but no prior position
        wifi = wifis[0]
        obs.extend([
            obs_factory(lat=wifi.lat + 0.001,
                        lon=wifi.lon + 0.001, mac=wifi.mac),
            obs_factory(lat=wifi.lat + 0.002,
                        lon=wifi.lon + 0.005, mac=wifi.mac),
            obs_factory(lat=wifi.lat + 0.003,
                        lon=wifi.lon + 0.009, mac=wifi.mac),
        ])
        wifi.lat = None
        wifi.lon = None
        wifi.samples = None
        wifi.weight = None
        # a wifi with a prior known position
        wifi = wifis[1]
        wifi.samples = 1
        wifi.weight = 1.0
        wifi.lat += 1.0
        wifi.lon += 1.0
        obs.extend([
            obs_factory(lat=wifi.lat + 0.01,
                        lon=wifi.lon, mac=wifi.mac),
            obs_factory(lat=wifi.lat + 0.07,
                        lon=wifi.lon, mac=wifi.mac),
        ])
        moving.add(wifi.mac)
        # a wifi with a very different prior position
        wifi = wifis[2]
        wifi.samples = 1
        wifi.weight = 1.0
        obs.extend([
            obs_factory(lat=wifi.lat + 2.0,
                        lon=wifi.lon, mac=wifi.mac),
            obs_factory(lat=wifi.lat + 2.002,
                        lon=wifi.lon, mac=wifi.mac),
        ])
        moving.add(wifi.mac)
        # an already blocked wifi
        wifi = wifis[3]
        wifi.block_last = now.date()
        wifi.block_count = 1
        obs.extend([
            obs_factory(lat=wifi.lat,
                        lon=wifi.lon, mac=wifi.mac),
            obs_factory(lat=wifi.lat + 0.1,
                        lon=wifi.lon, mac=wifi.mac),
        ])
        moving.add(wifi.mac)
        # a permanently blocked wifi
        wifi = wifis[4]
        wifi_lat, wifi_lon = (wifi.lat, wifi.lon)
        wifi.created = now - timedelta(days=57)
        wifi.block_first = (now - timedelta(days=35)).date()
        wifi.block_last = now.date() - 2 * TEMPORARY_BLOCKLIST_DURATION
        wifi.block_count = 2
        for col in ('lat', 'lon', 'max_lat', 'min_lat', 'max_lon', 'min_lon'):
            setattr(wifi, col, None)
        obs.extend([
            obs_factory(lat=wifi_lat, lon=wifi_lon, mac=wifi.mac),
        ])
        moving.add(wifi.mac)
        # a no longer blocked wifi
        wifi = wifis[5]
        wifi_lat, wifi_lon = (wifi.lat, wifi.lon)
        wifi.created = now - timedelta(days=46)
        wifi.block_last = now.date() - 2 * TEMPORARY_BLOCKLIST_DURATION
        wifi.block_count = 1
        for col in ('lat', 'lon', 'max_lat', 'min_lat', 'max_lon', 'min_lon'):
            setattr(wifi, col, None)
        obs.extend([
            obs_factory(lat=wifi_lat, lon=wifi_lon, mac=wifi.mac),
        ])
        # a no longer blocked wifi with disagreeing observations
        wifi = wifis[6]
        wifi_lat, wifi_lon = (wifi.lat, wifi.lon)
        wifi.created = now - timedelta(days=55)
        wifi.block_last = now.date() - 2 * TEMPORARY_BLOCKLIST_DURATION
        wifi.block_count = 1
        for col in ('lat', 'lon', 'max_lat', 'min_lat', 'max_lon', 'min_lon'):
            setattr(wifi, col, None)
        obs.extend([
            obs_factory(lat=wifi_lat, lon=wifi_lon, mac=wifi.mac),
            obs_factory(lat=wifi_lat + 2.0, lon=wifi_lon, mac=wifi.mac),
        ])
        moving.add(wifi.mac)
        self.session.commit()
        self._queue_and_update_wifi(obs)

        shards = set()
        for mac in moving:
            shards.add(WifiShard.shard_model(mac))
        blocks = []
        for shard in shards:
            for row in self.session.query(shard).all():
                if row.blocked(today=now.date()):
                    blocks.append(row)
        self.assertEqual(set([b.mac for b in blocks]), moving)

    def test_region(self):
        obs = []
        obs_factory = WifiObservationFactory
        wifi1 = WifiShardFactory(lat=46.2884, lon=6.77, region='FR')
        obs.extend(obs_factory.create_batch(
            5, mac=wifi1.mac, lat=wifi1.lat, lon=wifi1.lon + 0.05,
        ))
        wifi2 = WifiShardFactory(lat=46.2884, lon=7.4, region='FR')
        obs.extend(obs_factory.create_batch(
            5, mac=wifi2.mac, lat=wifi2.lat, lon=wifi2.lon + 0.05,
        ))
        self.session.commit()
        self._queue_and_update_wifi(obs)

        # position is really not in FR anymore, but still close enough
        # to not re-trigger region determination
        wifi1 = self.session.query(wifi1.__class__).get(wifi1.mac)
        self.assertEqual(wifi1.block_count, 0)
        self.assertEqual(wifi1.region, 'FR')
        wifi2 = self.session.query(wifi2.__class__).get(wifi2.mac)
        self.assertEqual(wifi1.block_count, 0)
        self.assertEqual(wifi2.region, 'CH')

    def test_weighted_update(self):
        wifi = WifiShardFactory(samples=2, weight=3.0)
        wifi_lat = wifi.lat
        wifi_lon = wifi.lon

        obs_factory = WifiObservationFactory
        obs = [
            obs_factory(lat=wifi.lat, lon=wifi.lon - 0.002,
                        accuracy=20.0, signal=-30, mac=wifi.mac),
            obs_factory(lat=wifi.lat, lon=wifi.lon - 0.004,
                        age=-8000, accuracy=40.0, signal=-60, mac=wifi.mac),
            obs_factory(lat=wifi.lat, lon=wifi.lon - 0.006,
                        age=1000, accuracy=10.0, signal=-90, mac=wifi.mac),
            obs_factory(lat=wifi.lat, lon=wifi.lon - 0.006,
                        accuracy=10.0, speed=20.0, mac=wifi.mac),
            obs_factory(lat=wifi.lat, lon=wifi.lon - 0.008,
                        age=40000, accuracy=10.0, mac=wifi.mac),
            obs_factory(lat=wifi.lat, lon=wifi.lon - 0.008,
                        accuracy=10.0, speed=50.1, mac=wifi.mac),
        ]

        self.session.commit()
        self._queue_and_update_wifi(obs)
        shard = WifiShard.shard_model(wifi.mac)
        wifis = self.session.query(shard).all()
        self.assertEqual(len(wifis), 1)
        wifi = wifis[0]
        self.assertAlmostEqual(wifi.lat, wifi_lat)
        self.assertAlmostEqual(wifi.max_lat, wifi_lat)
        self.assertAlmostEqual(wifi.min_lat, wifi_lat)
        self.assertAlmostEqual(wifi.lon, wifi_lon - 0.0019971, 7)
        self.assertAlmostEqual(wifi.max_lon, wifi_lon)
        self.assertAlmostEqual(wifi.min_lon, wifi_lon - 0.006)
        self.assertEqual(wifi.radius, 278)
        self.assertEqual(wifi.samples, 6)
        self.assertAlmostEqual(wifi.weight, 16.11, 2)
