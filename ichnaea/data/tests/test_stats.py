from datetime import timedelta

from ichnaea.cache import redis_pipeline
from ichnaea.data.tasks import statcounter_update
from ichnaea.models.content import (
    Stat,
    StatCounter,
    StatKey,
)
from ichnaea.tests.base import CeleryTestCase
from ichnaea import util


class TestStatCounter(CeleryTestCase):

    def setUp(self):
        super(TestStatCounter, self).setUp()
        self.today = util.utcnow().date()
        self.yesterday = self.today - timedelta(1)
        self.two_days = self.today - timedelta(2)

    def add_counter(self, stat_key, time, value):
        stat_counter = StatCounter(stat_key, time)
        with redis_pipeline(self.redis_client) as pipe:
            stat_counter.incr(pipe, value)

    def check_stat(self, stat_key, time, value):
        hashkey = Stat.to_hashkey(key=stat_key, time=time)
        stat = Stat.getkey(self.session, hashkey)
        self.assertEqual(stat.value, value)

    def test_first_run(self):
        self.add_counter(StatKey.cell, self.yesterday, 3)

        statcounter_update.delay(ago=1).get()
        self.check_stat(StatKey.cell, self.yesterday, 3)

    def test_update_from_yesterday(self):
        self.add_counter(StatKey.cell, self.yesterday, 3)
        self.add_counter(StatKey.cell, self.today, 4)
        self.session.add(Stat(key=StatKey.cell, time=self.two_days, value=2))
        self.session.flush()

        statcounter_update.delay(ago=1).get()
        self.check_stat(StatKey.cell, self.yesterday, 5)

    def test_multiple_updates_for_today(self):
        self.add_counter(StatKey.cell, self.today, 4)
        self.session.add(Stat(key=StatKey.cell, time=self.yesterday, value=5))
        self.session.flush()

        statcounter_update.delay(ago=0).get()
        self.check_stat(StatKey.cell, self.today, 9)

        self.add_counter(StatKey.cell, self.today, 3)
        statcounter_update.delay(ago=0).get()
        self.check_stat(StatKey.cell, self.today, 12)

    def test_update_with_gap(self):
        a_week_ago = self.today - timedelta(days=7)
        self.add_counter(StatKey.cell, self.yesterday, 3)
        self.add_counter(StatKey.cell, self.today, 4)
        self.session.add(Stat(key=StatKey.cell, time=a_week_ago, value=7))
        self.session.flush()

        statcounter_update.delay(ago=1).get()
        self.check_stat(StatKey.cell, self.yesterday, 10)

    def test_update_does_not_overwrite(self):
        self.add_counter(StatKey.cell, self.yesterday, 5)
        self.add_counter(StatKey.cell, self.today, 7)
        self.session.add(Stat(key=StatKey.cell, time=self.two_days, value=1))
        self.session.add(Stat(key=StatKey.cell, time=self.yesterday, value=3))
        self.session.flush()

        statcounter_update.delay(ago=1).get()
        self.check_stat(StatKey.cell, self.yesterday, 8)

    def test_update_all_keys(self):
        self.add_counter(StatKey.cell, self.yesterday, 2)
        self.add_counter(StatKey.wifi, self.yesterday, 3)
        self.add_counter(StatKey.unique_cell, self.yesterday, 4)
        self.add_counter(StatKey.unique_wifi, self.yesterday, 5)
        self.add_counter(StatKey.unique_ocid_cell, self.yesterday, 6)
        self.session.add(Stat(key=StatKey.cell, time=self.two_days, value=7))
        self.session.add(Stat(key=StatKey.wifi, time=self.two_days, value=8))
        self.session.flush()

        statcounter_update.delay(ago=1).get()
        self.check_stat(StatKey.cell, self.yesterday, 9)
        self.check_stat(StatKey.wifi, self.yesterday, 11)
        self.check_stat(StatKey.unique_cell, self.yesterday, 4)
        self.check_stat(StatKey.unique_wifi, self.yesterday, 5)
        self.check_stat(StatKey.unique_ocid_cell, self.yesterday, 6)
