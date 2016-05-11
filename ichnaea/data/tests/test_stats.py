from datetime import timedelta

from ichnaea.cache import redis_pipeline
from ichnaea.data.tasks import (
    update_statcounter,
    update_statregion,
)
from ichnaea.models import (
    Radio,
    RegionStat,
    Stat,
    StatCounter,
    StatKey,
)
from ichnaea.tests.base import CeleryTestCase
from ichnaea.tests.factories import (
    BlueShardFactory,
    CellAreaFactory,
    WifiShardFactory,
)
from ichnaea import util


class TestStatCounter(CeleryTestCase):

    @property
    def today(self):
        return util.utcnow().date()

    @property
    def yesterday(self):
        return self.today - timedelta(days=1)

    @property
    def two_days(self):
        return self.today - timedelta(days=2)

    def add_counter(self, stat_key, time, value):
        stat_counter = StatCounter(stat_key, time)
        with redis_pipeline(self.redis_client) as pipe:
            stat_counter.incr(pipe, value)

    def check_stat(self, stat_key, time, value):
        stat = (self.session.query(Stat)
                            .filter(Stat.key == stat_key)
                            .filter(Stat.time == time)).first()
        assert stat.value == value

    def test_first_run(self):
        self.add_counter(StatKey.cell, self.today, 3)

        update_statcounter.delay().get()
        self.check_stat(StatKey.cell, self.today, 3)

    def test_update_from_yesterday(self):
        self.add_counter(StatKey.cell, self.today, 4)
        self.session.add(Stat(key=StatKey.cell, time=self.yesterday, value=2))
        self.session.flush()

        update_statcounter.delay().get()
        self.check_stat(StatKey.cell, self.today, 6)

    def test_multiple_updates_for_today(self):
        self.add_counter(StatKey.cell, self.today, 4)
        self.session.add(Stat(key=StatKey.cell, time=self.yesterday, value=5))
        self.session.flush()

        update_statcounter.delay().get()
        self.check_stat(StatKey.cell, self.today, 9)

        self.add_counter(StatKey.cell, self.today, 3)
        update_statcounter.delay().get()
        self.check_stat(StatKey.cell, self.today, 12)

    def test_update_with_gap(self):
        a_week_ago = self.today - timedelta(days=7)
        self.add_counter(StatKey.cell, self.today, 3)
        self.session.add(Stat(key=StatKey.cell, time=a_week_ago, value=7))
        self.session.flush()

        update_statcounter.delay().get()
        self.check_stat(StatKey.cell, self.today, 10)

    def test_update_two_days(self):
        self.add_counter(StatKey.cell, self.yesterday, 5)
        self.add_counter(StatKey.cell, self.today, 7)
        self.session.add(Stat(key=StatKey.cell, time=self.two_days, value=1))
        self.session.add(Stat(key=StatKey.cell, time=self.yesterday, value=3))
        self.session.flush()

        update_statcounter.delay().get()
        self.check_stat(StatKey.cell, self.yesterday, 8)
        self.check_stat(StatKey.cell, self.today, 15)

    def test_update_all_keys(self):
        self.add_counter(StatKey.blue, self.today, 1)
        self.add_counter(StatKey.cell, self.today, 2)
        self.add_counter(StatKey.wifi, self.today, 3)
        self.add_counter(StatKey.unique_blue, self.today, 4)
        self.add_counter(StatKey.unique_cell, self.today, 5)
        self.add_counter(StatKey.unique_wifi, self.today, 6)
        self.add_counter(StatKey.unique_cell_ocid, self.today, 7)
        self.session.add(Stat(key=StatKey.blue, time=self.yesterday, value=8))
        self.session.add(Stat(key=StatKey.cell, time=self.yesterday, value=9))
        self.session.add(Stat(key=StatKey.wifi, time=self.yesterday, value=10))
        self.session.flush()

        update_statcounter.delay().get()
        self.check_stat(StatKey.blue, self.today, 9)
        self.check_stat(StatKey.cell, self.today, 11)
        self.check_stat(StatKey.wifi, self.today, 13)
        self.check_stat(StatKey.unique_blue, self.today, 4)
        self.check_stat(StatKey.unique_cell, self.today, 5)
        self.check_stat(StatKey.unique_wifi, self.today, 6)
        self.check_stat(StatKey.unique_cell_ocid, self.today, 7)


class TestStatRegion(CeleryTestCase):

    def test_empty(self):
        update_statregion.delay().get()
        stats = self.session.query(RegionStat).all()
        assert stats == []

    def test_update(self):
        area = CellAreaFactory(radio=Radio.gsm, num_cells=1)
        area.region = None
        BlueShardFactory.create_batch(2, region='CA')
        BlueShardFactory.create_batch(3, region='GB')
        CellAreaFactory(radio=Radio.gsm, region='DE', num_cells=1)
        CellAreaFactory(radio=Radio.gsm, region='DE', num_cells=2)
        CellAreaFactory(radio=Radio.gsm, region='CA', num_cells=2)
        CellAreaFactory(radio=Radio.wcdma, region='DE', num_cells=3)
        CellAreaFactory(radio=Radio.lte, region='CA', num_cells=4)
        WifiShardFactory.create_batch(5, region='DE')
        WifiShardFactory.create_batch(6, region='US')
        wifi = WifiShardFactory()
        wifi.region = None
        self.session.add(RegionStat(region='US', blue=1, wifi=2))
        self.session.add(RegionStat(region='TW', wifi=1))
        self.session.flush()

        update_statregion.delay().get()
        stats = self.session.query(RegionStat).all()
        assert len(stats) == 4

        for stat in stats:
            values = (stat.gsm, stat.wcdma, stat.lte, stat.blue, stat.wifi)
            if stat.region == 'DE':
                assert values == (3, 3, 0, 0, 5)
            elif stat.region == 'CA':
                assert values == (2, 0, 4, 2, 0)
            elif stat.region == 'GB':
                assert values == (0, 0, 0, 3, 0)
            elif stat.region == 'US':
                assert values == (0, 0, 0, 0, 6)
