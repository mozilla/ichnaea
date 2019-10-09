from datetime import timedelta

from ichnaea.data.tasks import monitor_api_key_limits, monitor_api_users
from ichnaea import util


class TestMonitor(object):
    def test_monitor_api_keys_empty(self, celery, metricsmock):
        monitor_api_key_limits.delay().get()
        assert not metricsmock.has_record("gauge", "api.limit")

    def test_monitor_api_keys_one(self, celery, redis, metricsmock):
        today = util.utcnow().strftime("%Y%m%d")
        rate_key = "apilimit:no_key_1:v1.geolocate:" + today
        redis.incr(rate_key, 13)

        monitor_api_key_limits.delay().get()
        assert metricsmock.has_record(
            "gauge", "api.limit", tags=["key:no_key_1", "path:v1.geolocate"]
        )

    def test_monitor_api_keys_multiple(self, celery, redis, metricsmock):
        now = util.utcnow()
        today = now.strftime("%Y%m%d")
        yesterday = (now - timedelta(hours=24)).strftime("%Y%m%d")
        data = {
            "test": {"v1.search": 11, "v1.geolocate": 13},
            "no_key_1": {"v1.search": 12},
            "no_key_2": {"v1.geolocate": 15},
        }
        for key, paths in data.items():
            for path, value in paths.items():
                rate_key = "apilimit:%s:%s:%s" % (key, path, today)
                redis.incr(rate_key, value)
                rate_key = "apilimit:%s:%s:%s" % (key, path, yesterday)
                redis.incr(rate_key, value - 10)

        # add some other items into Redis
        redis.lpush("default", 1, 2)
        redis.set("cache_something", "{}")

        monitor_api_key_limits.delay().get()
        assert (
            len(
                metricsmock.filter_records(
                    "gauge", "api.limit", tags=["key:test", "path:v1.geolocate"]
                )
            )
            == 1
        )
        assert (
            len(
                metricsmock.filter_records(
                    "gauge", "api.limit", tags=["key:test", "path:v1.search"]
                )
            )
            == 1
        )
        assert (
            len(
                metricsmock.filter_records(
                    "gauge", "api.limit", tags=["key:no_key_1", "path:v1.search"]
                )
            )
            == 1
        )
        assert (
            len(
                metricsmock.filter_records(
                    "gauge", "api.limit", tags=["key:no_key_2", "path:v1.geolocate"]
                )
            )
            == 1
        )


class TestMonitorAPIUsers(object):
    @property
    def today(self):
        return util.utcnow().date()

    @property
    def today_str(self):
        return self.today.strftime("%Y-%m-%d")

    def test_empty(self, celery, metricsmock):
        monitor_api_users.delay().get()
        assert not metricsmock.has_record("gauge", "submit.user")
        assert not metricsmock.has_record("gauge", "locate.user")

    def test_one_day(self, celery, geoip_data, redis, metricsmock):
        bhutan_ip = geoip_data["Bhutan"]["ip"]
        london_ip = geoip_data["London"]["ip"]
        redis.pfadd("apiuser:submit:test:" + self.today_str, bhutan_ip, london_ip)
        redis.pfadd("apiuser:submit:valid_key:" + self.today_str, bhutan_ip)
        redis.pfadd("apiuser:locate:valid_key:" + self.today_str, bhutan_ip)

        monitor_api_users.delay().get()
        assert metricsmock.has_record(
            "gauge", "submit.user", value=2, tags=["key:test", "interval:1d"]
        )
        assert metricsmock.has_record(
            "gauge", "submit.user", value=2, tags=["key:test", "interval:7d"]
        )
        assert metricsmock.has_record(
            "gauge", "submit.user", value=1, tags=["key:valid_key", "interval:1d"]
        )
        assert metricsmock.has_record(
            "gauge", "submit.user", value=1, tags=["key:valid_key", "interval:7d"]
        )
        assert metricsmock.has_record(
            "gauge", "locate.user", value=1, tags=["key:valid_key", "interval:1d"]
        )
        assert metricsmock.has_record(
            "gauge", "locate.user", value=1, tags=["key:valid_key", "interval:7d"]
        )

    def test_many_days(self, celery, geoip_data, redis, metricsmock):
        bhutan_ip = geoip_data["Bhutan"]["ip"]
        london_ip = geoip_data["London"]["ip"]
        days_6 = (self.today - timedelta(days=6)).strftime("%Y-%m-%d")
        days_7 = (self.today - timedelta(days=7)).strftime("%Y-%m-%d")
        redis.pfadd("apiuser:submit:test:" + self.today_str, "127.0.0.1", bhutan_ip)
        # add the same IPs + one new one again
        redis.pfadd("apiuser:submit:test:" + days_6, "127.0.0.1", bhutan_ip, london_ip)
        # add one entry which is too old
        redis.pfadd("apiuser:submit:test:" + days_7, bhutan_ip)

        monitor_api_users.delay().get()
        assert (
            len(
                metricsmock.filter_records(
                    "gauge", "submit.user", value=2, tags=["key:test", "interval:1d"]
                )
            )
            == 1
        )
        # We count unique IPs over the entire 7 day period, so it's just 3 uniques.
        assert (
            len(
                metricsmock.filter_records(
                    "gauge", "submit.user", value=3, tags=["key:test", "interval:7d"]
                )
            )
            == 1
        )

        # the too old key was deleted manually
        assert not redis.exists("apiuser:submit:test:" + days_7)
