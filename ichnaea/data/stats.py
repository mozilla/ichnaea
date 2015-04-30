from datetime import timedelta

from ichnaea.data.base import DataTask
from ichnaea.models.content import (
    Stat,
    StatCounter,
    StatKey,
)
from ichnaea import util


class StatCounterUpdater(DataTask):

    def __init__(self, task, session, pipe):
        DataTask.__init__(self, task, session)
        self.pipe = pipe
        self.today = util.utcnow().date()

    def update(self, ago=1):
        day = self.today - timedelta(days=ago)
        for stat_key in StatKey:
            self.update_key(stat_key, day)

    def update_key(self, stat_key, day):
        # determine the value from the day before
        query = (self.session.query(Stat)
                             .filter(Stat.key == stat_key)
                             .filter(Stat.time < day)
                             .order_by(Stat.time.desc()))
        before = query.first()
        old_value = 0
        if before:
            old_value = before.value

        # get the value from redis for the day in question
        stat_counter = StatCounter(stat_key, day)
        value = stat_counter.get(self.redis_client)

        # insert or update a new stat value
        hashkey = Stat.to_hashkey(key=stat_key, time=day)
        Stat.incr(self.session, hashkey, old_value, value)

        # queue the redis value to be decreased
        stat_counter.decr(self.pipe, value)
