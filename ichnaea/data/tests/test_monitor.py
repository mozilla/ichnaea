from datetime import timedelta

from ichnaea.data.tasks import (
    monitor_api_key_limits,
    monitor_api_users,
)
from ichnaea import util


class TestMonitor(object):

    def test_monitor_api_keys_empty(self, celery, stats):
        monitor_api_key_limits.delay().get()
        stats.check(gauge=[('api.limit', 0)])

    def test_monitor_api_keys_one(self, celery, redis, stats):
        today = util.utcnow().strftime('%Y%m%d')
        rate_key = 'apilimit:no_key_1:v1.geolocate:' + today
        redis.incr(rate_key, 13)

        monitor_api_key_limits.delay().get()
        stats.check(gauge=[
            ('api.limit', ['key:no_key_1', 'path:v1.geolocate']),
        ])

    def test_monitor_api_keys_multiple(self, celery, redis, stats):
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
                redis.incr(rate_key, value)
                rate_key = 'apilimit:%s:%s:%s' % (key, path, yesterday)
                redis.incr(rate_key, value - 10)

        # add some other items into Redis
        redis.lpush('default', 1, 2)
        redis.set('cache_something', '{}')

        monitor_api_key_limits.delay().get()
        stats.check(gauge=[
            ('api.limit', ['key:test', 'path:v1.geolocate']),
            ('api.limit', ['key:test', 'path:v1.search']),
            ('api.limit', ['key:no_key_1', 'path:v1.search']),
            ('api.limit', ['key:no_key_2', 'path:v1.geolocate']),
        ])


class TestMonitorAPIUsers(object):

    @property
    def today(self):
        return util.utcnow().date()

    @property
    def today_str(self):
        return self.today.strftime('%Y-%m-%d')

    def test_empty(self, celery, stats):
        monitor_api_users.delay().get()
        stats.check(gauge=[('submit.user', 0), ('locate.user', 0)])

    def test_one_day(self, celery, geoip_data, redis, stats):
        bhutan_ip = geoip_data['Bhutan']['ip']
        london_ip = geoip_data['London']['ip']
        redis.pfadd(
            'apiuser:submit:test:' + self.today_str, bhutan_ip, london_ip)
        redis.pfadd(
            'apiuser:submit:valid_key:' + self.today_str, bhutan_ip)
        redis.pfadd(
            'apiuser:locate:valid_key:' + self.today_str, bhutan_ip)

        monitor_api_users.delay().get()
        stats.check(gauge=[
            ('submit.user', 1, 2, ['key:test', 'interval:1d']),
            ('submit.user', 1, 2, ['key:test', 'interval:7d']),
            ('submit.user', 1, 1, ['key:valid_key', 'interval:1d']),
            ('submit.user', 1, 1, ['key:valid_key', 'interval:7d']),
            ('locate.user', 1, 1, ['key:valid_key', 'interval:1d']),
            ('locate.user', 1, 1, ['key:valid_key', 'interval:7d']),
        ])

    def test_many_days(self, celery, geoip_data, redis, stats):
        bhutan_ip = geoip_data['Bhutan']['ip']
        london_ip = geoip_data['London']['ip']
        days_6 = (self.today - timedelta(days=6)).strftime('%Y-%m-%d')
        days_7 = (self.today - timedelta(days=7)).strftime('%Y-%m-%d')
        redis.pfadd(
            'apiuser:submit:test:' + self.today_str, '127.0.0.1', bhutan_ip)
        # add the same IPs + one new one again
        redis.pfadd(
            'apiuser:submit:test:' + days_6, '127.0.0.1', bhutan_ip, london_ip)
        # add one entry which is too old
        redis.pfadd(
            'apiuser:submit:test:' + days_7, bhutan_ip)

        monitor_api_users.delay().get()
        stats.check(gauge=[
            ('submit.user', 1, 2, ['key:test', 'interval:1d']),
            # we count unique IPs over the entire 7 day period,
            # so it's just 3 uniques
            ('submit.user', 1, 3, ['key:test', 'interval:7d']),
        ])

        # the too old key was deleted manually
        assert not redis.exists('apiuser:submit:test:' + days_7)
