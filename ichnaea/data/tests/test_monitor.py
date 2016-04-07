from datetime import timedelta
from random import randint

from ichnaea.data.tasks import (
    monitor_api_key_limits,
    monitor_api_users,
    monitor_ocid_import,
    monitor_queue_size,
)
from ichnaea.models import Radio
from ichnaea.tests.base import CeleryTestCase
from ichnaea.tests.factories import CellShardOCIDFactory
from ichnaea import util


class TestMonitor(CeleryTestCase):

    def test_monitor_api_keys_empty(self):
        monitor_api_key_limits.delay().get()
        self.check_stats(gauge=[('api.limit', 0)])

    def test_monitor_api_keys_one(self):
        today = util.utcnow().strftime('%Y%m%d')
        rate_key = 'apilimit:no_key_1:v1.geolocate:' + today
        self.redis_client.incr(rate_key, 13)

        monitor_api_key_limits.delay().get()
        self.check_stats(gauge=[
            ('api.limit', ['key:no_key_1', 'path:v1.geolocate']),
        ])

    def test_monitor_api_keys_multiple(self):
        now = util.utcnow()
        today = now.strftime('%Y%m%d')
        yesterday = (now - timedelta(hours=24)).strftime('%Y%m%d')
        data = {
            'test': {'v1.search': 11, 'v1.geolocate': 13},
            'no_key_1': {'v1.search': 12},
            'no_key_2': {'v1.geolocate': 15},
        }
        for key, paths in data.items():
            for path, value in paths.items():
                rate_key = 'apilimit:%s:%s:%s' % (key, path, today)
                self.redis_client.incr(rate_key, value)
                rate_key = 'apilimit:%s:%s:%s' % (key, path, yesterday)
                self.redis_client.incr(rate_key, value - 10)

        # add some other items into Redis
        self.redis_client.lpush('default', 1, 2)
        self.redis_client.set('cache_something', '{}')

        monitor_api_key_limits.delay().get()
        self.check_stats(gauge=[
            ('api.limit', ['key:test', 'path:v1.geolocate']),
            ('api.limit', ['key:test', 'path:v1.search']),
            ('api.limit', ['key:no_key_1', 'path:v1.search']),
            ('api.limit', ['key:no_key_2', 'path:v1.geolocate']),
        ])

    def test_monitor_ocid_import(self):
        now = util.utcnow()
        for radio, i in [(Radio.gsm, 21),
                         (Radio.wcdma, 16),
                         (Radio.gsm, 20),
                         (Radio.lte, 1)]:
            CellShardOCIDFactory(radio=radio, created=now - timedelta(hours=i))
            self.session.flush()
            monitor_ocid_import.delay().get()

        self.check_stats(gauge=[('table', 4, ['table:cell_ocid_age'])])

    def test_monitor_queue_size(self):
        data = {
            'export_queue_internal': 3,
            'export_queue_backup:abcd-ef-1234': 7,
        }
        for name in self.celery_app.all_queues:
            data[name] = randint(1, 10)

        for k, v in data.items():
            self.redis_client.lpush(k, *range(v))

        monitor_queue_size.delay().get()
        self.check_stats(
            gauge=[('queue', 1, v, ['queue:' + k]) for k, v in data.items()])


class TestMonitorAPIUsers(CeleryTestCase):

    def setUp(self):
        super(TestMonitorAPIUsers, self).setUp()
        self.today = util.utcnow().date()
        self.today_str = util.utcnow().date().strftime('%Y-%m-%d')
        self.bhutan_ip = self.geoip_data['Bhutan']['ip']
        self.london_ip = self.geoip_data['London']['ip']

    def test_empty(self):
        monitor_api_users.delay().get()
        self.check_stats(gauge=[('submit.user', 0), ('locate.user', 0)])

    def test_one_day(self):
        self.redis_client.pfadd(
            'apiuser:submit:test:' + self.today_str,
            self.bhutan_ip, self.london_ip)
        self.redis_client.pfadd(
            'apiuser:submit:valid_key:' + self.today_str,
            self.bhutan_ip)
        self.redis_client.pfadd(
            'apiuser:locate:valid_key:' + self.today_str,
            self.bhutan_ip)

        monitor_api_users.delay().get()
        self.check_stats(gauge=[
            ('submit.user', 1, 2, ['key:test', 'interval:1d']),
            ('submit.user', 1, 2, ['key:test', 'interval:7d']),
            ('submit.user', 1, 1, ['key:valid_key', 'interval:1d']),
            ('submit.user', 1, 1, ['key:valid_key', 'interval:7d']),
            ('locate.user', 1, 1, ['key:valid_key', 'interval:1d']),
            ('locate.user', 1, 1, ['key:valid_key', 'interval:7d']),
        ])

    def test_many_days(self):
        days_6 = (self.today - timedelta(days=6)).strftime('%Y-%m-%d')
        days_7 = (self.today - timedelta(days=7)).strftime('%Y-%m-%d')
        self.redis_client.pfadd(
            'apiuser:submit:test:' + self.today_str,
            '127.0.0.1', self.bhutan_ip)
        # add the same IPs + one new one again
        self.redis_client.pfadd(
            'apiuser:submit:test:' + days_6,
            '127.0.0.1', self.bhutan_ip, self.london_ip)
        # add one entry which is too old
        self.redis_client.pfadd(
            'apiuser:submit:test:' + days_7, self.bhutan_ip)

        monitor_api_users.delay().get()
        self.check_stats(gauge=[
            ('submit.user', 1, 2, ['key:test', 'interval:1d']),
            # we count unique IPs over the entire 7 day period,
            # so it's just 3 uniques
            ('submit.user', 1, 3, ['key:test', 'interval:7d']),
        ])

        # the too old key was deleted manually
        self.assertFalse(
            self.redis_client.exists('apiuser:submit:test:' + days_7))
