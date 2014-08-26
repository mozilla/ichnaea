from datetime import timedelta

from ichnaea.monitor.tasks import (
    monitor_api_key_limits,
    monitor_queue_length,
)
from ichnaea.tests.base import CeleryTestCase
from ichnaea import util


class TestMonitorTasks(CeleryTestCase):

    def test_monitor_api_key_limits(self):
        redis_client = self.redis_client
        now = util.utcnow()
        today = now.strftime("%Y%m%d")
        yesterday = (now - timedelta(hours=24)).strftime("%Y%m%d")
        data = {
            'test': 11,
            'no_key_1': 12,
            'no_key_2': 15,
        }
        for k, v in data.items():
            key = "apilimit:%s:%s" % (k, today)
            redis_client.incr(key, v)
            key = "apilimit:%s:%s" % (k, yesterday)
            redis_client.incr(key, v - 10)

        # add some other items into Redis
        redis_client.lpush('default', 1, 2)
        redis_client.set('cache_something', '{}')

        result = monitor_api_key_limits.delay().get()

        self.check_stats(
            gauge=['apilimit.' + k for k in data.keys()],
        )
        self.assertEqual(result, data)

    def test_monitor_queue_length(self):
        data = {
            'default': 2,
            'incoming': 3,
            'insert': 5,
            'monitor': 1,
        }
        for k, v in data.items():
            self.redis_client.lpush(k, *range(v))

        result = monitor_queue_length.delay().get()

        self.check_stats(
            gauge=['queue.' + k for k in data.keys()],
        )
        self.assertEqual(result, data)
