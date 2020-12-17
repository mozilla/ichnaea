from collections import defaultdict
from datetime import datetime, timedelta
from unittest import mock

import pytest
from pymysql.err import MySQLError
from zoneinfo import ZoneInfo
from sqlalchemy.exc import InterfaceError

from geocalc import destination
from ichnaea.data.station import CellUpdater
from ichnaea.data.tasks import update_blue, update_cell, update_wifi
from ichnaea.models import (
    decode_cellid,
    encode_cellarea,
    BlueShard,
    CellShard,
    Radio,
    ReportSource,
    station_blocked,
    StatCounter,
    StatKey,
    WifiShard,
)
from ichnaea.models.constants import BLUE_MAX_RADIUS, CELL_MAX_RADIUS, WIFI_MAX_RADIUS
from ichnaea.tests.factories import (
    BlueObservationFactory,
    BlueShardFactory,
    CellObservationFactory,
    CellShardFactory,
    WifiObservationFactory,
    WifiShardFactory,
)
from ichnaea.tests.test_db import RETRIABLES
from ichnaea import util

UTC = ZoneInfo("UTC")


class BaseStationTest:

    queue_prefix = None
    shard_model = None
    unique_key = None

    def check_statcounter(self, redis, stat_key, value):
        stat_counter = StatCounter(stat_key, util.utcnow())
        assert stat_counter.get(redis) == value

    def _queue_and_update(self, celery, obs, task):
        sharded_obs = defaultdict(list)
        for ob in obs:
            sharded_obs[self.shard_model.shard_id(getattr(ob, self.unique_key))].append(
                ob
            )

        for shard_id, values in sharded_obs.items():
            queue = celery.data_queues[self.queue_prefix + shard_id]
            queue.enqueue([value.to_json() for value in values])
            task.delay(shard_id=shard_id).get()


class TestDatabaseErrors(BaseStationTest):
    queue_prefix = "update_cell_"
    shard_model = CellShard
    unique_key = "cellid"

    @pytest.mark.parametrize(
        "errclass,errno,errmsg", list(RETRIABLES.values()), ids=list(RETRIABLES.keys())
    )
    def test_retriable_exceptions(
        self,
        celery,
        redis,
        session,
        db_shared_session,
        metricsmock,
        errclass,
        errno,
        errmsg,
        backoff_sleep_mock,
    ):
        """Test database exceptions where the task should wait and try again."""

        obs = CellObservationFactory.build(radio=Radio.lte)
        shard = CellShard.shard_model(obs.cellid)
        cell = CellShardFactory.build(
            radio=obs.radio,
            mcc=obs.mcc,
            mnc=obs.mnc,
            lac=obs.lac,
            cid=obs.cid,
            samples=10,
            created=datetime(2019, 12, 5, tzinfo=UTC),
        )
        session.add(cell)
        session.commit()
        session.begin_nested()  # Protect test cell from task rollback

        error = errclass(errno, errmsg)
        wrapped = InterfaceError.instance(
            statement="SELECT COUNT(*) FROM cell_area",
            params={},
            orig=error,
            dbapi_base_err=MySQLError,
        )
        with mock.patch.object(
            CellUpdater, "add_area_update", side_effect=[wrapped, None]
        ):
            self._queue_and_update(celery, [obs], update_cell)
            assert CellUpdater.add_area_update.call_count == 2
            backoff_sleep_mock.assert_called_once()

        cells = session.query(shard).all()
        assert len(cells) == 1
        self.check_statcounter(redis, StatKey.cell, 1)

        # The existing cell record was updated
        cell = cells[0]
        assert cell.samples == 11
        assert cell.created == datetime(2019, 12, 5, tzinfo=UTC)
        self.check_statcounter(redis, StatKey.unique_cell, 0)

        # Assert generated metrics are correct
        metricsmock.assert_incr_once(
            "data.observation.insert", value=1, tags=["type:cell"]
        )
        metricsmock.assert_incr_once(
            "data.station.confirm", value=1, tags=["type:cell"]
        )
        metricsmock.assert_timing_once("task", tags=["task:data.update_cell"])
        metricsmock.assert_incr_once(
            "data.station.dberror", tags=["type:cell", "errno:%s" % errno]
        )


class StationTest(BaseStationTest):

    max_radius = None
    obs_factory = None
    stat_obs_key = None
    stat_station_key = None
    station_factory = None
    type_tag = None

    @property
    def now(self):
        return util.utcnow()

    @property
    def today(self):
        return self.now.date()

    @property
    def ten_days(self):
        return self.now - timedelta(days=10)

    @property
    def past(self):
        return self.now - timedelta(days=50)

    @property
    def one_year(self):
        return self.now - timedelta(days=367)

    def displace(self, lat, lon, bearing=0.0, distance=0.0):
        distance = (self.max_radius + 10.0) * distance
        return destination(lat, lon, bearing, distance)

    def make_obs(self, source=ReportSource.gnss, distance=0.0):
        # Return three observations, either all at the same place (0.0),
        # or one in the center and the other two to the north/south.
        # With distance 0.5, the two observations are both close enough
        # to the center to individually be consistent with the center
        # position, but too far apart combined. With distance 1.0 each
        # observation is too far apart from the center on its own.
        obs = []
        obs.append(self.obs_factory.build(source=source))

        lat, lon = self.displace(obs[0].lat, obs[0].lon, 0.0, distance)
        obs.append(
            self.obs_factory(lat=lat, lon=lon, source=source, **self.key(obs[0]))
        )

        lat, lon = self.displace(obs[0].lat, obs[0].lon, 180.0, distance)
        obs.append(
            self.obs_factory(lat=lat, lon=lon, source=source, **self.key(obs[0]))
        )

        return obs

    def get_station(self, session, model):
        shard = self.shard_model.shard_model(getattr(model, self.unique_key))
        return (
            session.query(shard).filter(
                getattr(shard, self.unique_key) == getattr(model, self.unique_key)
            )
        ).first()

    def check_areas(self, celery, obs):
        pass

    def check_blocked(self, station, first=None, last=None, count=None):
        assert station.block_first == first
        assert station.block_last == last
        assert station.block_count == count

    def check_dates(self, station, created, modified, last_seen=None):
        assert station.created.date() == created
        assert station.modified.date() == modified
        assert station.last_seen == last_seen

    def check_no_position(self, station):
        assert station.last_seen is None
        assert station.lat is None
        assert station.lon is None
        assert station.max_lat is None
        assert station.min_lat is None
        assert station.max_lon is None
        assert station.min_lon is None
        assert station.radius is None
        assert station.samples is None
        assert station.source is None
        assert station.weight is None

    def test_blocklist_skip(self, celery, redis, session):
        observations = self.obs_factory.build_batch(3)
        self.station_factory(
            created=self.now,
            block_first=self.ten_days.date(),
            block_last=self.today,
            block_count=1,
            **self.key(observations[0]),
        )
        session.commit()
        self.queue_and_update(celery, observations)

        blocks = []
        for obs in observations:
            cell = self.get_station(session, obs)
            if station_blocked(cell):
                blocks.append(cell)

        assert len(blocks) == 1
        self.check_blocked(blocks[0], self.ten_days.date(), self.today, 1)

        self.check_areas(celery, [observations[1], observations[2]])
        self.check_statcounter(redis, self.stat_obs_key, 3)
        self.check_statcounter(redis, self.stat_station_key, 2)

    @pytest.mark.parametrize("source", (ReportSource.gnss, ReportSource.query))
    def test_new(self, celery, session, metricsmock, source):
        obs = self.obs_factory.build(source=source)
        obs1 = self.obs_factory(lat=obs.lat + 0.0001, source=source, **self.key(obs))
        obs2 = self.obs_factory(lat=obs.lat - 0.0003, source=source, **self.key(obs))
        obs3 = self.obs_factory(lon=obs.lon + 0.0002, source=source, **self.key(obs))
        obs4 = self.obs_factory(lon=obs.lon - 0.0004, source=source, **self.key(obs))
        self.queue_and_update(celery, [obs, obs1, obs2, obs3, obs4])

        self.check_areas(celery, [obs])
        station = self.get_station(session, obs)
        assert station.lat == pytest.approx(obs.lat - 0.00004)
        assert station.max_lat == pytest.approx(obs.lat + 0.0001)
        assert station.min_lat == pytest.approx(obs.lat - 0.0003)
        assert station.lon == pytest.approx(obs.lon - 0.00004)
        assert station.max_lon == pytest.approx(obs.lon + 0.0002)
        assert station.min_lon == pytest.approx(obs.lon - 0.0004)
        assert station.radius == 38
        assert station.region == "GB"
        assert station.samples == 5
        assert station.source == source
        assert station.weight == pytest.approx(5.0)
        self.check_blocked(station, None)
        self.check_dates(station, self.today, self.today, self.today)

        metricsmock.assert_incr_once(
            "data.observation.insert", value=5, tags=[self.type_tag]
        )
        metricsmock.assert_incr_once("data.station.new", value=1, tags=[self.type_tag])

    @pytest.mark.parametrize("source", (ReportSource.gnss, ReportSource.query))
    def test_new_block(self, celery, session, source):
        obs = self.make_obs(source=source, distance=1.0)
        self.queue_and_update(celery, obs)

        obs = obs[0]
        self.check_areas(celery, [obs])
        station = self.get_station(session, obs)
        self.check_blocked(station, self.today, self.today, 1)
        self.check_dates(station, self.today, self.today)
        self.check_no_position(station)

    @pytest.mark.parametrize("source", (ReportSource.gnss, ReportSource.query))
    def test_no_position_change(self, celery, session, source):
        obs = self.make_obs(source=source)
        self.station_factory(
            block_first=self.past.date(),
            block_last=self.past.date(),
            block_count=1,
            created=self.past,
            modified=self.past,
            last_seen=None,
            lat=None,
            lon=None,
            max_lat=None,
            min_lat=None,
            max_lon=None,
            min_lon=None,
            radius=None,
            region=None,
            source=None,
            samples=None,
            weight=None,
            **self.key(obs[0]),
        )
        session.commit()
        self.queue_and_update(celery, obs)

        obs = obs[0]
        self.check_areas(celery, [obs])
        station = self.get_station(session, obs)
        assert station.lat == obs.lat
        assert station.max_lat == obs.lat
        assert station.min_lat == obs.lat
        assert station.lon == pytest.approx(obs.lon)
        assert station.max_lon == obs.lon
        assert station.min_lon == obs.lon
        assert station.radius == 0
        assert station.region == "GB"
        assert station.source == source
        assert station.samples == 3
        assert station.weight == 3.0
        self.check_blocked(station, self.past.date(), self.past.date(), 1)
        self.check_dates(station, self.past.date(), self.today, self.today)

    @pytest.mark.parametrize("source", (ReportSource.gnss, ReportSource.query))
    def test_no_position_ignore(self, celery, session, source):
        obs = self.make_obs(source=source, distance=1.0)
        self.station_factory(
            block_first=self.past.date(),
            block_last=self.past.date(),
            block_count=1,
            created=self.past,
            modified=self.past,
            last_seen=None,
            lat=None,
            lon=None,
            max_lat=None,
            min_lat=None,
            max_lon=None,
            min_lon=None,
            radius=None,
            region=None,
            source=None,
            samples=None,
            weight=None,
            **self.key(obs[0]),
        )
        session.commit()
        self.queue_and_update(celery, obs)

        obs = obs[0]
        self.check_areas(celery, [])
        station = self.get_station(session, obs)
        assert station.modified.date() == self.past.date()
        self.check_blocked(station, self.past.date(), self.past.date(), 1)
        self.check_no_position(station)

    def test_confirm(self, celery, session):
        obs1 = self.obs_factory.build(source=ReportSource.query)
        self.station_factory(
            created=self.now, modified=self.now, last_seen=self.today, **self.key(obs1)
        )
        obs2 = self.obs_factory.build(source=ReportSource.query)
        self.station_factory(
            created=self.ten_days,
            modified=self.ten_days,
            last_seen=self.ten_days.date(),
            **self.key(obs2),
        )
        session.commit()
        self.queue_and_update(celery, [obs1, obs2])

        self.check_areas(celery, [])
        station = self.get_station(session, obs1)
        self.check_dates(station, self.today, self.today, self.today)

        station = self.get_station(session, obs2)
        self.check_dates(
            station, self.ten_days.date(), self.ten_days.date(), self.today
        )

    @pytest.mark.parametrize("obs_source", (ReportSource.gnss, ReportSource.query))
    @pytest.mark.parametrize("station_source", (ReportSource.gnss, ReportSource.query))
    def test_block_half_consistent_obs(
        self, celery, session, obs_source, station_source
    ):
        obs = self.make_obs(source=obs_source, distance=0.5)
        self.station_factory(
            lat=obs[0].lat,
            lon=obs[0].lon,
            created=self.past,
            modified=self.past,
            source=station_source,
            **self.key(obs[0]),
        )
        session.commit()
        self.queue_and_update(celery, obs)

        obs = obs[0]
        self.check_areas(celery, [obs])
        station = self.get_station(session, obs)
        self.check_blocked(station, self.today, self.today, 1)
        self.check_dates(station, self.past.date(), self.today)
        self.check_no_position(station)

    @pytest.mark.parametrize("obs_source", (ReportSource.gnss, ReportSource.query))
    @pytest.mark.parametrize("station_source", (ReportSource.gnss, ReportSource.query))
    def test_block_consistent_obs(self, celery, session, obs_source, station_source):
        obs = self.make_obs(source=obs_source)
        lat, lon = self.displace(obs[0].lat, obs[0].lon, distance=1.0)
        self.station_factory(
            lat=lat,
            lon=lon,
            created=self.past,
            modified=self.past,
            source=station_source,
            **self.key(obs[0]),
        )
        session.commit()
        self.queue_and_update(celery, obs)

        obs = obs[0]
        self.check_areas(celery, [obs])
        station = self.get_station(session, obs)
        assert station.region == "GB"
        self.check_blocked(station, self.today, self.today, 1)
        self.check_dates(station, self.past.date(), self.today)
        self.check_no_position(station)

    @pytest.mark.parametrize("obs_source", (ReportSource.gnss, ReportSource.query))
    @pytest.mark.parametrize("station_source", (ReportSource.gnss, ReportSource.query))
    def test_block_inconsistent_obs(self, celery, session, obs_source, station_source):
        obs = self.make_obs(source=obs_source, distance=1.0)
        self.station_factory(
            created=self.ten_days,
            modified=self.ten_days,
            last_seen=self.ten_days.date(),
            source=station_source,
            **self.key(obs[0]),
        )
        session.commit()
        self.queue_and_update(celery, obs)

        obs = obs[0]
        self.check_areas(celery, [obs])
        station = self.get_station(session, obs)
        assert station.region == "GB"
        self.check_blocked(station, self.today, self.today, 1)
        self.check_dates(station, self.ten_days.date(), self.today)
        self.check_no_position(station)

    @pytest.mark.parametrize("obs_source", (ReportSource.gnss, ReportSource.query))
    @pytest.mark.parametrize("station_source", (ReportSource.gnss, ReportSource.query))
    def test_block_inconsistent_obs_old_station(
        self, celery, session, obs_source, station_source
    ):
        obs = self.make_obs(source=obs_source, distance=1.0)
        self.station_factory(
            created=self.one_year,
            modified=self.one_year,
            last_seen=self.one_year.date(),
            source=station_source,
            **self.key(obs[0]),
        )
        session.commit()
        self.queue_and_update(celery, obs)

        obs = obs[0]
        self.check_areas(celery, [obs])
        station = self.get_station(session, obs)
        assert station.region == "GB"
        self.check_blocked(station, self.today, self.today, 1)
        self.check_dates(station, self.one_year.date(), self.today)
        self.check_no_position(station)

    def test_replace_query_station(self, celery, session):
        obs = self.make_obs(source=ReportSource.gnss)
        self.station_factory(
            samples=10,
            weight=15.0,
            created=self.ten_days,
            modified=self.ten_days,
            last_seen=self.ten_days.date(),
            source=ReportSource.query,
            **self.key(obs[0]),
        )
        session.commit()
        self.queue_and_update(celery, obs)

        obs = obs[0]
        self.check_areas(celery, [obs])
        station = self.get_station(session, obs)
        self.check_blocked(station, None)
        self.check_dates(station, self.ten_days.date(), self.today, self.today)
        assert station.lat == obs.lat
        assert station.max_lat == obs.lat
        assert station.min_lat == obs.lat
        assert station.lon == pytest.approx(obs.lon)
        assert station.max_lon == obs.lon
        assert station.min_lon == obs.lon
        assert station.radius == 0
        assert station.region == "GB"
        assert station.samples == 3
        assert station.source == ReportSource.gnss
        assert station.weight == pytest.approx(3.0)

    @pytest.mark.parametrize("obs_source", (ReportSource.gnss, ReportSource.query))
    @pytest.mark.parametrize("station_source", (ReportSource.gnss, ReportSource.query))
    def test_replace_old_station(self, celery, session, obs_source, station_source):
        obs = self.make_obs(source=obs_source)
        lat, lon = self.displace(obs[0].lat, obs[0].lon, distance=1.0)
        self.station_factory(
            lat=lat,
            lon=lon,
            created=self.one_year,
            modified=self.one_year,
            last_seen=self.one_year.date(),
            source=station_source,
            **self.key(obs[0]),
        )
        session.commit()
        self.queue_and_update(celery, obs)

        obs = obs[0]
        self.check_areas(celery, [obs])
        station = self.get_station(session, obs)

        self.check_blocked(station, None)
        self.check_dates(station, self.one_year.date(), self.today, self.today)
        assert station.lat == obs.lat
        assert station.max_lat == obs.lat
        assert station.min_lat == obs.lat
        assert station.lon == pytest.approx(obs.lon)
        assert station.max_lon == obs.lon
        assert station.min_lon == obs.lon
        assert station.radius == 0
        assert station.region == "GB"
        assert station.samples == 3
        assert station.source == obs_source


class StationMacTest(StationTest):

    unique_key = "mac"

    def key(self, model):
        return {"mac": model.mac}


class TestBlue(StationMacTest):

    max_radius = BLUE_MAX_RADIUS
    obs_factory = BlueObservationFactory
    queue_prefix = "update_blue_"
    shard_model = BlueShard
    stat_obs_key = StatKey.blue
    stat_station_key = StatKey.unique_blue
    station_factory = BlueShardFactory
    type_tag = "type:blue"

    def queue_and_update(self, celery, obs):
        return super(TestBlue, self)._queue_and_update(celery, obs, update_blue)

    @pytest.mark.parametrize("source", (ReportSource.gnss, ReportSource.query))
    def test_change(self, celery, session, source):
        station = self.station_factory(samples=2, weight=3.0, source=source)
        station_key = self.key(station)
        lat = station.lat
        lon = station.lon
        obs = [
            self.obs_factory(
                lat=lat,
                lon=lon - 0.0001,
                accuracy=20.0,
                signal=-30,
                source=source,
                **station_key,
            ),
            self.obs_factory(
                lat=lat,
                lon=lon - 0.0002,
                age=-8000,
                accuracy=40.0,
                signal=-60,
                source=source,
                **station_key,
            ),
            self.obs_factory(
                lat=lat, lon=lon - 0.0003, accuracy=100.1, source=source, **station_key
            ),
        ]
        session.commit()
        self.queue_and_update(celery, obs)

        station = self.get_station(session, station)
        assert station.lat == lat
        assert station.max_lat == lat
        assert station.min_lat == lat
        assert station.lon == pytest.approx(lon - 0.0000305)
        assert station.max_lon == lon
        assert station.min_lon == pytest.approx(lon - 0.0002)
        assert station.radius == 12
        assert station.samples == 4
        assert station.source == source
        assert station.weight == pytest.approx(3.957107)


class TestWifi(StationMacTest):

    max_radius = WIFI_MAX_RADIUS
    obs_factory = WifiObservationFactory
    queue_prefix = "update_wifi_"
    shard_model = WifiShard
    stat_obs_key = StatKey.wifi
    stat_station_key = StatKey.unique_wifi
    station_factory = WifiShardFactory
    type_tag = "type:wifi"

    def queue_and_update(self, celery, obs):
        return super(TestWifi, self)._queue_and_update(celery, obs, update_wifi)

    @pytest.mark.parametrize("source", (ReportSource.gnss, ReportSource.query))
    def test_change(self, celery, session, source):
        station = self.station_factory(samples=2, weight=3.0, source=source)
        station_key = self.key(station)
        lat = station.lat
        lon = station.lon
        obs = [
            self.obs_factory(
                lat=lat,
                lon=lon - 0.002,
                accuracy=20.0,
                signal=-30,
                source=source,
                **station_key,
            ),
            self.obs_factory(
                lat=lat,
                lon=lon - 0.004,
                age=-8000,
                accuracy=40.0,
                signal=-60,
                source=source,
                **station_key,
            ),
            self.obs_factory(
                lat=lat,
                lon=lon - 0.006,
                age=1000,
                accuracy=10.0,
                signal=-90,
                source=source,
                **station_key,
            ),
            self.obs_factory(
                lat=lat,
                lon=lon - 0.006,
                accuracy=10.0,
                speed=20.0,
                source=source,
                **station_key,
            ),
            self.obs_factory(
                lat=lat,
                lon=lon - 0.008,
                age=40000,
                accuracy=10.0,
                source=source,
                **station_key,
            ),
            self.obs_factory(
                lat=lat,
                lon=lon - 0.008,
                accuracy=10.0,
                speed=50.1,
                source=source,
                **station_key,
            ),
            self.obs_factory(
                lat=lat, lon=lon - 0.010, accuracy=200.1, source=source, **station_key
            ),
        ]
        session.commit()
        self.queue_and_update(celery, obs)

        station = self.get_station(session, station)
        assert station.lat == pytest.approx(lat)
        assert station.max_lat == lat
        assert station.min_lat == lat
        assert station.lon == pytest.approx(lon - 0.0019971)
        assert station.max_lon == lon
        assert station.min_lon == pytest.approx(lon - 0.006)
        assert station.radius == 278
        assert station.samples == 6
        assert station.source == source
        assert station.weight == pytest.approx(16.10707)

    def test_region(self, celery, session):
        obs = []
        station1 = self.station_factory(lat=46.2884, lon=6.77, region="FR")
        obs.extend(
            self.obs_factory.create_batch(
                5, lat=station1.lat, lon=station1.lon + 0.05, **self.key(station1)
            )
        )
        station2 = self.station_factory(lat=46.2884, lon=7.4, region="FR")
        obs.extend(
            self.obs_factory.create_batch(
                5, lat=station2.lat, lon=station2.lon + 0.05, **self.key(station2)
            )
        )
        session.commit()
        self.queue_and_update(celery, obs)

        # position is really not in FR anymore, but still close enough
        # to not re-trigger region determination
        station1 = self.get_station(session, station1)
        self.check_blocked(station1, None)
        assert station1.region == "FR"
        station2 = self.get_station(session, station2)
        self.check_blocked(station2, None)
        assert station2.region == "CH"


class TestCell(StationTest):

    max_radius = CELL_MAX_RADIUS
    obs_factory = CellObservationFactory
    queue_prefix = "update_cell_"
    shard_model = CellShard
    stat_obs_key = StatKey.cell
    stat_station_key = StatKey.unique_cell
    station_factory = CellShardFactory
    type_tag = "type:cell"
    unique_key = "cellid"

    def key(self, model):
        return {
            "radio": model.radio,
            "mcc": model.mcc,
            "mnc": model.mnc,
            "lac": model.lac,
            "cid": model.cid,
        }

    def queue_and_update(self, celery, obs):
        return self._queue_and_update(celery, obs, update_cell)

    def check_areas(self, celery, obs):
        queue = celery.data_queues["update_cellarea"]
        queued = set(queue.dequeue())
        cellids = [decode_cellid(ob.unique_key) for ob in obs]
        areaids = set([encode_cellarea(*cellid[:4]) for cellid in cellids])
        assert queued == areaids

    @pytest.mark.parametrize("source", (ReportSource.gnss, ReportSource.query))
    def test_change(self, celery, session, source):
        station = self.station_factory(
            radio=Radio.gsm, samples=1, source=source, weight=2.0
        )
        station_key = self.key(station)
        lat = station.lat
        lon = station.lon
        obs = [
            self.obs_factory(
                lat=lat,
                lon=lon - 0.002,
                accuracy=20.0,
                signal=-51,
                source=source,
                **station_key,
            ),
            self.obs_factory(
                lat=lat,
                signal=-111,
                lon=lon - 0.004,
                accuracy=1000.0,
                source=source,
                **station_key,
            ),
            self.obs_factory(
                lat=lat, lon=lon - 0.004, accuracy=1000.1, source=source, **station_key
            ),
        ]
        session.commit()
        self.queue_and_update(celery, obs)

        obs = obs[0]
        self.check_areas(celery, [obs])
        station = self.get_station(session, station)
        assert station.lat == pytest.approx(lat)
        assert station.max_lat == lat
        assert station.min_lat == lat
        assert station.lon == pytest.approx(lon - 0.0015793)
        assert station.max_lon == lon
        assert station.min_lon == pytest.approx(lon - 0.004)
        assert station.radius == 168
        assert station.samples == 3
        assert station.source == source
        assert station.weight == pytest.approx(9.2452954)
