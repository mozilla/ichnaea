from datetime import timedelta

from ichnaea.cache import redis_pipeline
from ichnaea.data.tasks import cleanup_stat, update_statcounter, update_statregion
from ichnaea.models import Radio, RegionStat, Stat, StatCounter, StatKey
from ichnaea.tests.factories import BlueShardFactory, CellAreaFactory, WifiShardFactory
from ichnaea import util


class TestStatCounter(object):
    @property
    def today(self):
        return util.utcnow().date()

    @property
    def yesterday(self):
        return self.today - timedelta(days=1)

    @property
    def two_days(self):
        return self.today - timedelta(days=2)

    def add_counter(self, redis, stat_key, time, value):
        stat_counter = StatCounter(stat_key, time)
        with redis_pipeline(redis) as pipe:
            stat_counter.incr(pipe, value)

    def check_stat(self, session, stat_key, time, value):
        stat = (
            session.query(Stat).filter(Stat.key == stat_key).filter(Stat.time == time)
        ).first()
        assert stat.value == value

    def test_first_run(self, celery, redis, session):
        self.add_counter(redis, StatKey.cell, self.today, 3)

        update_statcounter.delay().get()
        self.check_stat(session, StatKey.cell, self.today, 3)

    def test_update_from_yesterday(self, celery, redis, session):
        self.add_counter(redis, StatKey.cell, self.today, 4)
        session.add(Stat(key=StatKey.cell, time=self.yesterday, value=2))
        session.flush()

        update_statcounter.delay().get()
        self.check_stat(session, StatKey.cell, self.today, 6)

    def test_multiple_updates_for_today(self, celery, redis, session):
        self.add_counter(redis, StatKey.cell, self.today, 4)
        session.add(Stat(key=StatKey.cell, time=self.yesterday, value=5))
        session.flush()

        update_statcounter.delay().get()
        self.check_stat(session, StatKey.cell, self.today, 9)

        self.add_counter(redis, StatKey.cell, self.today, 3)
        update_statcounter.delay().get()
        self.check_stat(session, StatKey.cell, self.today, 12)

    def test_update_with_gap(self, celery, redis, session):
        a_week_ago = self.today - timedelta(days=7)
        self.add_counter(redis, StatKey.cell, self.today, 3)
        session.add(Stat(key=StatKey.cell, time=a_week_ago, value=7))
        session.flush()

        update_statcounter.delay().get()
        self.check_stat(session, StatKey.cell, self.today, 10)

    def test_update_two_days(self, celery, redis, session):
        self.add_counter(redis, StatKey.cell, self.yesterday, 5)
        self.add_counter(redis, StatKey.cell, self.today, 7)
        session.add(Stat(key=StatKey.cell, time=self.two_days, value=1))
        session.add(Stat(key=StatKey.cell, time=self.yesterday, value=3))
        session.flush()

        update_statcounter.delay().get()
        self.check_stat(session, StatKey.cell, self.yesterday, 8)
        self.check_stat(session, StatKey.cell, self.today, 15)

    def test_update_all_keys(self, celery, redis, session):
        self.add_counter(redis, StatKey.blue, self.today, 1)
        self.add_counter(redis, StatKey.cell, self.today, 2)
        self.add_counter(redis, StatKey.wifi, self.today, 3)
        self.add_counter(redis, StatKey.unique_blue, self.today, 4)
        self.add_counter(redis, StatKey.unique_cell, self.today, 5)
        self.add_counter(redis, StatKey.unique_wifi, self.today, 6)
        session.add(Stat(key=StatKey.blue, time=self.yesterday, value=8))
        session.add(Stat(key=StatKey.cell, time=self.yesterday, value=9))
        session.add(Stat(key=StatKey.wifi, time=self.yesterday, value=10))
        session.flush()

        update_statcounter.delay().get()
        self.check_stat(session, StatKey.blue, self.today, 9)
        self.check_stat(session, StatKey.cell, self.today, 11)
        self.check_stat(session, StatKey.wifi, self.today, 13)
        self.check_stat(session, StatKey.unique_blue, self.today, 4)
        self.check_stat(session, StatKey.unique_cell, self.today, 5)
        self.check_stat(session, StatKey.unique_wifi, self.today, 6)


class TestStatCleaner(object):
    @property
    def today(self):
        return util.utcnow().date()

    def _one(self, key, time):
        return Stat(key=key, time=time, value=1)

    def test_empty(self, celery, session):
        cleanup_stat.delay().get()
        assert session.query(Stat).count() == 0

    def test_cleanup(self, celery, session):
        session.add_all(
            [
                self._one(StatKey.cell, self.today),
                self._one(StatKey.cell, self.today - timedelta(days=366 * 2)),
                self._one(StatKey.wifi, self.today),
                self._one(StatKey.wifi, self.today - timedelta(days=366 * 2)),
                self._one(StatKey.blue, self.today),
                self._one(StatKey.blue, self.today - timedelta(days=366 * 2)),
                self._one(StatKey.unique_blue, self.today),
                self._one(StatKey.unique_blue, self.today - timedelta(days=366)),
            ]
        )
        session.flush()

        cleanup_stat.delay().get()
        assert session.query(Stat).count() == 5


class TestStatRegion(object):
    def test_empty(self, celery, session):
        update_statregion.delay().get()
        stats = session.query(RegionStat).all()
        assert stats == []

    def test_update(self, celery, session):
        area = CellAreaFactory(radio=Radio.gsm, num_cells=1)
        area.region = None
        BlueShardFactory.create_batch(2, region="CA")
        BlueShardFactory.create_batch(3, region="GB")
        CellAreaFactory(radio=Radio.gsm, region="DE", num_cells=1)
        CellAreaFactory(radio=Radio.gsm, region="DE", num_cells=2)
        CellAreaFactory(radio=Radio.gsm, region="CA", num_cells=2)
        CellAreaFactory(radio=Radio.wcdma, region="DE", num_cells=3)
        CellAreaFactory(radio=Radio.lte, region="CA", num_cells=4)
        WifiShardFactory.create_batch(5, region="DE")
        WifiShardFactory.create_batch(6, region="US")
        wifi = WifiShardFactory()
        wifi.region = None
        session.add(RegionStat(region="US", blue=1, wifi=2))
        session.add(RegionStat(region="TW", wifi=1))
        session.flush()

        update_statregion.delay().get()
        stats = session.query(RegionStat).all()
        assert len(stats) == 4

        for stat in stats:
            values = (stat.gsm, stat.wcdma, stat.lte, stat.blue, stat.wifi)
            if stat.region == "DE":
                assert values == (3, 3, 0, 0, 5)
            elif stat.region == "CA":
                assert values == (2, 0, 4, 2, 0)
            elif stat.region == "GB":
                assert values == (0, 0, 0, 3, 0)
            elif stat.region == "US":
                assert values == (0, 0, 0, 0, 6)
