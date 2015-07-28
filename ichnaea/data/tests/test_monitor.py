from datetime import timedelta
from random import randint

from ichnaea.models import ApiKey
from ichnaea.data.tasks import (
    monitor_api_key_limits,
    monitor_ocid_import,
    monitor_queue_length,
)
from ichnaea.tests.base import CeleryTestCase
from ichnaea.tests.factories import OCIDCellFactory
from ichnaea import util


class TestMonitorTasks(CeleryTestCase):

    def test_monitor_api_keys_empty(self):
        result = monitor_api_key_limits.delay().get()
        self.assertEqual(result, {})

    def test_monitor_api_keys_one(self):
        redis_client = self.redis_client
        now = util.utcnow()
        today = now.strftime('%Y%m%d')

        key = 'apilimit:no_key_1:' + today
        redis_client.incr(key, 13)

        result = monitor_api_key_limits.delay().get()
        self.assertEqual(result, {'no_key_1': 13})

        self.check_stats(gauge=[
            ('api.limit', ['key:no_key_1']),
        ])

    def test_monitor_api_keys_multiple(self):
        redis_client = self.redis_client
        now = util.utcnow()
        today = now.strftime('%Y%m%d')
        yesterday = (now - timedelta(hours=24)).strftime('%Y%m%d')
        data = {
            'test': 11,
            'no_key_1': 12,
            'no_key_2': 15,
        }
        for k, v in data.items():
            key = 'apilimit:%s:%s' % (k, today)
            redis_client.incr(key, v)
            key = 'apilimit:%s:%s' % (k, yesterday)
            redis_client.incr(key, v - 10)

        api_keys = [
            ApiKey(valid_key='no_key_1', shortname='shortname_1'),
            ApiKey(valid_key='no_key_2'),
            ApiKey(valid_key='no_key_3', shortname='shortname_3'),
        ]
        self.session.add_all(api_keys)
        self.session.flush()

        # add some other items into Redis
        redis_client.lpush('default', 1, 2)
        redis_client.set('cache_something', '{}')

        result = monitor_api_key_limits.delay().get()

        self.check_stats(gauge=[
            ('api.limit', ['key:test']),
            ('api.limit', ['key:shortname_1']),
            ('api.limit', ['key:no_key_2']),
        ])
        self.assertDictEqual(
            result, {'test': 11, 'shortname_1': 12, 'no_key_2': 15})

    def test_monitor_ocid_import(self):
        now = util.utcnow()
        expected = []
        results = []
        for i in range(35, 5, -5):
            created = now - timedelta(hours=i)
            expected.append(i * 3600000)
            OCIDCellFactory(created=created, cid=i)
            self.session.flush()
            results.append(monitor_ocid_import.delay().get())

        self.check_stats(gauge=[
            ('table', len(expected), ['name:ocid_cell_age']),
        ])
        for result, expect in zip(results, expected):
            # The values should be almost equal, ignoring differences
            # less than 10 seconds (or 9999 milliseconds / 4 places)
            self.assertAlmostEqual(result, expect, -4)

    def test_monitor_queue_length(self):
        data = {}
        for name in self.celery_app.all_queues:
            data[name] = randint(1, 10)

        for k, v in data.items():
            self.redis_client.lpush(k, *range(v))

        result = monitor_queue_length.delay().get()

        self.check_stats(
            gauge=[('queue', 1, v, ['name:' + k]) for k, v in data.items()],
        )
        self.assertEqual(result, data)
