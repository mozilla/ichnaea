from ichnaea.monitor.tasks import monitor_queue_length
from ichnaea.tests.base import CeleryTestCase


class TestMonitorTasks(CeleryTestCase):

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
