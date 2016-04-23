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
from ichnaea.geocalc import destination
from ichnaea.models import (
    BlueShard,
    CellShard,
    Radio,
    ReportSource,
    StatCounter,
    StatKey,
    WifiShard,
)
from ichnaea.models.constants import (
    BLUE_MAX_RADIUS,
    CELL_MAX_RADIUS,
    WIFI_MAX_RADIUS,
)
from ichnaea.tests.base import CeleryTestCase
from ichnaea.tests.factories import (
    BlueObservationFactory,
    BlueShardFactory,
    CellObservationFactory,
    CellShardFactory,
    WifiObservationFactory,
    WifiShardFactory,
)
from ichnaea import util


class BaseStationTest(object):

    queue_prefix = None
    shard_model = None
    unique_key = None

    def _compare_sets(self, one, two):
        self.assertEqual(set(one), set(two))

    def check_statcounter(self, stat_key, value):
        stat_counter = StatCounter(stat_key, util.utcnow())
        self.assertEqual(stat_counter.get(self.redis_client), value)

    def _queue_and_update(self, obs, task):
        sharded_obs = defaultdict(list)
        for ob in obs:
            sharded_obs[self.shard_model.shard_id(
                getattr(ob, self.unique_key))].append(ob)

        for shard_id, values in sharded_obs.items():
            queue = self.celery_app.data_queues[self.queue_prefix + shard_id]
            queue.enqueue([value.to_json() for value in values])
            task.delay(shard_id=shard_id).get()


class TestDatabaseErrors(BaseStationTest, CeleryTestCase):
    # this is a standalone class to ensure DB isolation

    queue_prefix = 'update_cell_'
    shard_model = CellShard
    unique_key = 'cellid'

    def queue_and_update(self, obs):
        return self._queue_and_update(obs, update_cell)

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
            CellUpdater._retry_wait = 0.0001
            self.session.execute('set session innodb_lock_wait_timeout = 1')
            with mock.patch.object(CellUpdater, 'add_area_update', mock_area):
                self.queue_and_update([obs])
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


class StationTest(BaseStationTest):

    max_radius = None
    obs_factory = None
    stat_obs_key = None
    stat_station_key = None
    station_factory = None
    type_tag = None

    def get_station(self, model):
        shard = self.shard_model.shard_model(getattr(model, self.unique_key))
        return (self.session.query(shard)
                            .filter(getattr(shard, self.unique_key) ==
                                    getattr(model, self.unique_key))).first()

    def test_blocklist_skip(self):
        now = util.utcnow()
        today = now.date()
        ten_days = today - timedelta(days=10)
        observations = self.obs_factory.build_batch(3)
        self.station_factory(
            created=now,
            block_first=ten_days,
            block_last=today,
            block_count=1,
            **self.key(observations[0])
        )
        self.session.commit()
        self.queue_and_update(observations)

        blocks = []
        for obs in observations:
            cell = self.get_station(obs)
            if cell.blocked():
                blocks.append(cell)

        self.assertEqual(len(blocks), 1)
        self.assertEqual(blocks[0].block_first, ten_days)
        self.assertEqual(blocks[0].block_last, today)
        self.assertEqual(blocks[0].block_count, 1)

        self.check_statcounter(self.stat_obs_key, 3)
        self.check_statcounter(self.stat_station_key, 2)

    def test_change_from_blocked(self):
        now = util.utcnow()
        past = now - timedelta(days=50)
        obs = self.obs_factory()
        self.station_factory(
            block_first=past.date(), block_last=past.date(),
            block_count=1, created=past, modified=past, last_seen=None,
            lat=None, lon=None,
            max_lat=None, min_lat=None, max_lon=None, min_lon=None,
            radius=None, region=None, source=None, samples=None, weight=None,
            **self.key(obs)
        )
        self.session.commit()
        self.queue_and_update([obs])

        station = self.get_station(obs)
        self.assertEqual(station.block_first, past.date())
        self.assertEqual(station.block_last, past.date())
        self.assertEqual(station.block_count, 1)
        self.assertEqual(station.created.date(), past.date())
        self.assertEqual(station.modified.date(), now.date())
        self.assertEqual(station.last_seen, now.date())
        self.assertEqual(station.lat, obs.lat)
        self.assertEqual(station.max_lat, obs.lat)
        self.assertEqual(station.min_lat, obs.lat)
        self.assertEqual(station.lon, obs.lon)
        self.assertEqual(station.max_lon, obs.lon)
        self.assertEqual(station.min_lon, obs.lon)
        self.assertEqual(station.radius, 0)
        self.assertEqual(station.region, 'GB')
        self.assertEqual(station.source, ReportSource.gnss)
        self.assertEqual(station.samples, 1)
        self.assertEqual(station.weight, 1.0)

    def test_confirm(self):
        now = util.utcnow()
        today = now.date()
        two_weeks = now - timedelta(days=14)
        obs1 = self.obs_factory.build(source=ReportSource.query)

        far_away_lat, _ = destination(
            obs1.lat, obs1.lon, 0.0, self.max_radius + 1000.0)

        obs11 = self.obs_factory.build(
            source=ReportSource.query,
            lat=far_away_lat, lon=obs1.lon, **self.key(obs1))
        obs2 = self.obs_factory.build(source=ReportSource.query)
        obs3 = self.obs_factory.build(source=ReportSource.query)
        self.station_factory(
            created=two_weeks, modified=two_weeks, last_seen=two_weeks.date(),
            **self.key(obs1))
        self.station_factory(
            created=now, modified=now, last_seen=today,
            **self.key(obs2))
        self.station_factory(
            created=two_weeks, modified=two_weeks, last_seen=two_weeks.date(),
            lat=far_away_lat, lon=obs3.lon, **self.key(obs3))
        self.session.commit()
        self.queue_and_update([obs1, obs11, obs2, obs3])

        station = self.get_station(obs1)
        self.assertEqual(station.created.date(), two_weeks.date())
        self.assertEqual(station.modified.date(), two_weeks.date())
        self.assertEqual(station.last_seen, today)

        station = self.get_station(obs2)
        self.assertEqual(station.created.date(), today)
        self.assertEqual(station.modified.date(), today)
        self.assertEqual(station.last_seen, today)

        self.check_stats(counter=[
            ('data.station.blocklist', 1, [self.type_tag]),
            ('data.station.confirm', 1, [self.type_tag]),
        ])

    def test_new(self):
        now = util.utcnow()
        obs = self.obs_factory.build()
        obs1 = self.obs_factory(lat=obs.lat + 0.0001, **self.key(obs))
        obs2 = self.obs_factory(lat=obs.lat - 0.0003, **self.key(obs))
        obs3 = self.obs_factory(lon=obs.lon + 0.0002, **self.key(obs))
        obs4 = self.obs_factory(lon=obs.lon - 0.0004, **self.key(obs))
        self.queue_and_update([obs, obs1, obs2, obs3, obs4])

        station = self.get_station(obs)
        self.assertAlmostEqual(station.lat, obs.lat - 0.00004)
        self.assertAlmostEqual(station.max_lat, obs.lat + 0.0001)
        self.assertAlmostEqual(station.min_lat, obs.lat - 0.0003)
        self.assertAlmostEqual(station.lon, obs.lon - 0.00004)
        self.assertAlmostEqual(station.max_lon, obs.lon + 0.0002)
        self.assertAlmostEqual(station.min_lon, obs.lon - 0.0004)
        self.assertEqual(station.radius, 38)
        self.assertEqual(station.region, 'GB')
        self.assertEqual(station.samples, 5)
        self.assertEqual(station.source, ReportSource.gnss)
        self.assertAlmostEqual(station.weight, 5.0, 2)
        self.assertEqual(station.created.date(), now.date())
        self.assertEqual(station.modified.date(), now.date())
        self.assertEqual(station.last_seen, now.date())
        self.assertEqual(station.block_first, None)
        self.assertEqual(station.block_last, None)
        self.assertEqual(station.block_count, None)

        self.check_stats(counter=[
            ('data.observation.insert', 1, [self.type_tag]),
            ('data.station.new', 1, [self.type_tag]),
        ])

    def test_new_query(self):
        now = util.utcnow()
        obs = self.obs_factory.build(source=ReportSource.query)
        obs1 = self.obs_factory.build(
            source=ReportSource.query, lat=obs.lat + 0.0003, **self.key(obs))
        obs2 = self.obs_factory.build(
            source=ReportSource.query, lon=obs.lon - 0.0003, **self.key(obs))
        self.queue_and_update([obs, obs1, obs2])

        station = self.get_station(obs)
        self.assertAlmostEqual(station.lat, obs.lat + 0.0001)
        self.assertAlmostEqual(station.max_lat, obs.lat + 0.0003)
        self.assertAlmostEqual(station.min_lat, obs.lat)
        self.assertAlmostEqual(station.lon, obs.lon - 0.0001)
        self.assertAlmostEqual(station.max_lon, obs.lon)
        self.assertAlmostEqual(station.min_lon, obs.lon - 0.0003)
        self.assertEqual(station.radius, 26)
        self.assertEqual(station.region, 'GB')
        self.assertEqual(station.samples, 3)
        self.assertEqual(station.source, ReportSource.query)
        self.assertAlmostEqual(station.weight, 3.0, 2)
        self.assertEqual(station.created.date(), now.date())
        self.assertEqual(station.modified.date(), now.date())
        self.assertEqual(station.last_seen, now.date())
        self.assertEqual(station.block_first, None)
        self.assertEqual(station.block_last, None)
        self.assertEqual(station.block_count, None)

        self.check_stats(counter=[
            ('data.observation.insert', 1, [self.type_tag]),
            ('data.station.new', 1, [self.type_tag]),
        ])

    def test_new_move(self):
        now = util.utcnow()
        today = now.date()
        obs1 = self.obs_factory.build()
        far_away_lat, _ = destination(
            obs1.lat, obs1.lon, 0.0, self.max_radius + 1000.0)
        obs2 = self.obs_factory(
            lat=far_away_lat, lon=obs1.lon, **self.key(obs1))
        self.queue_and_update([obs1, obs2])

        station = self.get_station(obs1)
        self.assertEqual(station.block_first, today)
        self.assertEqual(station.block_last, today)
        self.assertEqual(station.block_count, 1)
        self.assertEqual(station.created.date(), today)
        self.assertEqual(station.modified.date(), today)
        self.assertEqual(station.last_seen, None)
        self.assertEqual(station.lat, None)
        self.assertEqual(station.lon, None)

    def test_new_move_query(self):
        now = util.utcnow()
        today = now.date()
        obs1 = self.obs_factory.build(source=ReportSource.query)
        far_away_lat, _ = destination(
            obs1.lat, obs1.lon, 0.0, self.max_radius + 1000.0)
        obs2 = self.obs_factory(
            lat=far_away_lat, lon=obs1.lon, source=ReportSource.query,
            **self.key(obs1))
        self.queue_and_update([obs1, obs2])

        station = self.get_station(obs1)
        self.assertEqual(station.block_first, today)
        self.assertEqual(station.block_last, today)
        self.assertEqual(station.block_count, 1)
        self.assertEqual(station.created.date(), today)
        self.assertEqual(station.modified.date(), today)
        self.assertEqual(station.last_seen, None)
        self.assertEqual(station.lat, None)
        self.assertEqual(station.lon, None)

    def test_move_obs_agree(self):
        now = util.utcnow()
        today = now.date()
        past = now - timedelta(days=50)
        obs = self.obs_factory()
        far_away_lat, _ = destination(
            obs.lat, obs.lon, 0.0, self.max_radius + 1000.0)
        self.station_factory(
            lat=far_away_lat, created=past, modified=past, **self.key(obs))
        self.session.commit()
        self.queue_and_update([obs])

        station = self.get_station(obs)
        self.assertEqual(station.block_first, today)
        self.assertEqual(station.block_last, today)
        self.assertEqual(station.block_count, 1)
        self.assertEqual(station.created.date(), past.date())
        self.assertEqual(station.modified.date(), today)
        self.assertEqual(station.last_seen, None)
        self.assertEqual(station.lat, None)
        self.assertEqual(station.lon, None)
        self.assertEqual(station.region, 'GB')

    def test_move_obs_disagree(self):
        now = util.utcnow()
        today = now.date()
        past = now - timedelta(days=10)
        obs1 = self.obs_factory.build()
        far_away_lat, _ = destination(
            obs1.lat, obs1.lon, 0.0, self.max_radius + 1000.0)
        obs2 = self.obs_factory(
            lat=far_away_lat, lon=obs1.lon, **self.key(obs1))
        self.station_factory(
            created=past, modified=past, last_seen=past.date(),
            **self.key(obs1))
        self.session.commit()
        self.queue_and_update([obs1, obs2])

        station = self.get_station(obs1)
        self.assertEqual(station.block_first, today)
        self.assertEqual(station.block_last, today)
        self.assertEqual(station.block_count, 1)
        self.assertEqual(station.created.date(), past.date())
        self.assertEqual(station.modified.date(), today)
        self.assertEqual(station.last_seen, None)
        self.assertEqual(station.lat, None)
        self.assertEqual(station.lon, None)


class StationMacTest(StationTest):

    unique_key = 'mac'

    def key(self, model):
        return {'mac': model.mac}


class TestBlue(StationMacTest, CeleryTestCase):

    max_radius = BLUE_MAX_RADIUS
    obs_factory = BlueObservationFactory
    queue_prefix = 'update_blue_'
    shard_model = BlueShard
    stat_obs_key = StatKey.blue
    stat_station_key = StatKey.unique_blue
    station_factory = BlueShardFactory
    type_tag = 'type:blue'

    def queue_and_update(self, obs):
        return super(TestBlue, self)._queue_and_update(obs, update_blue)

    def test_change(self):
        station = self.station_factory(samples=2, weight=3.0)
        station_key = self.key(station)
        lat = station.lat
        lon = station.lon
        obs = [
            self.obs_factory(
                lat=lat, lon=lon - 0.0001,
                accuracy=20.0, signal=-30, **station_key),
            self.obs_factory(
                lat=lat, lon=lon - 0.0002,
                age=-8000, accuracy=40.0, signal=-60, **station_key),
        ]
        self.session.commit()
        self.queue_and_update(obs)

        station = self.get_station(station)
        self.assertAlmostEqual(station.lat, lat)
        self.assertAlmostEqual(station.max_lat, lat)
        self.assertAlmostEqual(station.min_lat, lat)
        self.assertAlmostEqual(station.lon, lon - 0.0000305, 7)
        self.assertAlmostEqual(station.max_lon, lon)
        self.assertAlmostEqual(station.min_lon, lon - 0.0002)
        self.assertEqual(station.radius, 12)
        self.assertEqual(station.samples, 4)
        self.assertAlmostEqual(station.weight, 3.96, 2)


class TestWifi(StationMacTest, CeleryTestCase):

    max_radius = WIFI_MAX_RADIUS
    obs_factory = WifiObservationFactory
    queue_prefix = 'update_wifi_'
    shard_model = WifiShard
    stat_obs_key = StatKey.wifi
    stat_station_key = StatKey.unique_wifi
    station_factory = WifiShardFactory
    type_tag = 'type:wifi'

    def queue_and_update(self, obs):
        return super(TestWifi, self)._queue_and_update(obs, update_wifi)

    def test_change(self):
        station = self.station_factory(samples=2, weight=3.0)
        station_key = self.key(station)
        lat = station.lat
        lon = station.lon
        obs = [
            self.obs_factory(
                lat=lat, lon=lon - 0.002,
                accuracy=20.0, signal=-30, **station_key),
            self.obs_factory(
                lat=lat, lon=lon - 0.004,
                age=-8000, accuracy=40.0, signal=-60, **station_key),
            self.obs_factory(
                lat=lat, lon=lon - 0.006,
                age=1000, accuracy=10.0, signal=-90, **station_key),
            self.obs_factory(
                lat=lat, lon=lon - 0.006,
                accuracy=10.0, speed=20.0, **station_key),
            self.obs_factory(
                lat=lat, lon=lon - 0.008,
                age=40000, accuracy=10.0, **station_key),
            self.obs_factory(
                lat=lat, lon=lon - 0.008,
                accuracy=10.0, speed=50.1, **station_key),
        ]
        self.session.commit()
        self.queue_and_update(obs)

        station = self.get_station(station)
        self.assertAlmostEqual(station.lat, lat)
        self.assertAlmostEqual(station.max_lat, lat)
        self.assertAlmostEqual(station.min_lat, lat)
        self.assertAlmostEqual(station.lon, lon - 0.0019971, 7)
        self.assertAlmostEqual(station.max_lon, lon)
        self.assertAlmostEqual(station.min_lon, lon - 0.006)
        self.assertEqual(station.radius, 278)
        self.assertEqual(station.samples, 6)
        self.assertAlmostEqual(station.weight, 16.11, 2)

    def test_region(self):
        obs = []
        station1 = self.station_factory(lat=46.2884, lon=6.77, region='FR')
        obs.extend(self.obs_factory.create_batch(
            5, lat=station1.lat, lon=station1.lon + 0.05,
            **self.key(station1)
        ))
        station2 = self.station_factory(lat=46.2884, lon=7.4, region='FR')
        obs.extend(self.obs_factory.create_batch(
            5, lat=station2.lat, lon=station2.lon + 0.05,
            **self.key(station2)
        ))
        self.session.commit()
        self.queue_and_update(obs)

        # position is really not in FR anymore, but still close enough
        # to not re-trigger region determination
        station1 = self.get_station(station1)
        self.assertEqual(station1.block_count, 0)
        self.assertEqual(station1.region, 'FR')
        station2 = self.get_station(station2)
        self.assertEqual(station2.block_count, 0)
        self.assertEqual(station2.region, 'CH')


class TestCell(StationTest, CeleryTestCase):

    max_radius = CELL_MAX_RADIUS
    obs_factory = CellObservationFactory
    queue_prefix = 'update_cell_'
    shard_model = CellShard
    stat_obs_key = StatKey.cell
    stat_station_key = StatKey.unique_cell
    station_factory = CellShardFactory
    type_tag = 'type:cell'
    unique_key = 'cellid'

    def key(self, model):
        return {
            'radio': model.radio, 'mcc': model.mcc, 'mnc': model.mnc,
            'lac': model.lac, 'cid': model.cid,
        }

    def queue_and_update(self, obs):
        return self._queue_and_update(obs, update_cell)

    def test_change(self):
        station = self.station_factory(radio=Radio.gsm, samples=1, weight=2.0)
        station_key = self.key(station)
        lat = station.lat
        lon = station.lon
        obs = [
            self.obs_factory(
                lat=lat, lon=lon - 0.002,
                accuracy=20.0, signal=-51, **station_key),
            self.obs_factory(
                lat=lat, signal=-111, lon=lon - 0.004,
                accuracy=40.0, **station_key),
        ]
        self.session.commit()
        self.queue_and_update(obs)

        station = self.get_station(station)
        self.assertAlmostEqual(station.lat, lat)
        self.assertAlmostEqual(station.max_lat, lat)
        self.assertAlmostEqual(station.min_lat, lat)
        self.assertAlmostEqual(station.lon, lon - 0.0016358, 7)
        self.assertAlmostEqual(station.max_lon, lon)
        self.assertAlmostEqual(station.min_lon, lon - 0.004)
        self.assertEqual(station.radius, 164)
        self.assertEqual(station.samples, 3)
        self.assertAlmostEqual(station.weight, 9.47, 2)
