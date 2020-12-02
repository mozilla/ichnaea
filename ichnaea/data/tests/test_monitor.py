from datetime import timedelta
import random

from ichnaea.data.tasks import (
    monitor_api_key_limits,
    monitor_api_users,
    monitor_queue_size,
    sentry_test,
)
from ichnaea import util


class TestMonitorApiKeys:
    def test_monitor_api_keys_empty(self, celery, metricsmock):
        monitor_api_key_limits.delay().get()
        metricsmock.assert_not_gauge("api.limit")

    def test_monitor_api_keys_one(self, celery, redis, metricsmock):
        today = util.utcnow().strftime("%Y%m%d")
        rate_key = "apilimit:no_key_1:v1.geolocate:" + today
        redis.incr(rate_key, 13)

        monitor_api_key_limits.delay().get()
        metricsmock.assert_gauge_once(
            "api.limit", value=13, tags=["key:no_key_1", "path:v1.geolocate"]
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
        metricsmock.assert_gauge_once(
            "api.limit", value=13, tags=["key:test", "path:v1.geolocate"]
        )
        metricsmock.assert_gauge_once(
            "api.limit", value=11, tags=["key:test", "path:v1.search"]
        )
        metricsmock.assert_gauge_once(
            "api.limit", value=12, tags=["key:no_key_1", "path:v1.search"]
        )
        metricsmock.assert_gauge_once(
            "api.limit", value=15, tags=["key:no_key_2", "path:v1.geolocate"]
        )


class TestMonitorAPIUsers:
    @property
    def today(self):
        return util.utcnow().date()

    @property
    def today_str(self):
        return self.today.strftime("%Y-%m-%d")

    def test_empty(self, celery, metricsmock):
        monitor_api_users.delay().get()
        metricsmock.assert_not_gauge("submit.user")
        metricsmock.assert_not_gauge("locate.user")

    def test_one_day(self, celery, geoip_data, redis, metricsmock):
        bhutan_ip = geoip_data["Bhutan"]["ip"]
        london_ip = geoip_data["London"]["ip"]
        redis.pfadd("apiuser:submit:test:" + self.today_str, bhutan_ip, london_ip)
        redis.pfadd("apiuser:submit:valid_key:" + self.today_str, bhutan_ip)
        redis.pfadd("apiuser:locate:valid_key:" + self.today_str, bhutan_ip)

        monitor_api_users.delay().get()
        metricsmock.assert_gauge_once(
            "submit.user", value=2, tags=["key:test", "interval:1d"]
        )
        metricsmock.assert_gauge_once(
            "submit.user", value=2, tags=["key:test", "interval:7d"]
        )
        metricsmock.assert_gauge_once(
            "submit.user", value=1, tags=["key:valid_key", "interval:1d"]
        )
        metricsmock.assert_gauge_once(
            "submit.user", value=1, tags=["key:valid_key", "interval:7d"]
        )
        metricsmock.assert_gauge_once(
            "locate.user", value=1, tags=["key:valid_key", "interval:1d"]
        )
        metricsmock.assert_gauge_once(
            "locate.user", value=1, tags=["key:valid_key", "interval:7d"]
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
        metricsmock.assert_gauge_once(
            "submit.user", value=2, tags=["key:test", "interval:1d"]
        )
        # We count unique IPs over the entire 7 day period, so it's just 3 uniques.
        metricsmock.assert_gauge_once(
            "submit.user", value=3, tags=["key:test", "interval:7d"]
        )

        # the too old key was deleted manually
        assert not redis.exists("apiuser:submit:test:" + days_7)


class TestMonitorQueueSize:
    expected_queues = {
        "celery_blue": ["task"],
        "celery_cell": ["task"],
        "celery_content": ["task"],
        "celery_default": ["task"],
        "celery_export": ["task"],
        "celery_monitor": ["task"],
        "celery_reports": ["task"],
        "celery_wifi": ["task"],
        "update_blue_0": ["data", "bluetooth"],
        "update_blue_1": ["data", "bluetooth"],
        "update_blue_2": ["data", "bluetooth"],
        "update_blue_3": ["data", "bluetooth"],
        "update_blue_4": ["data", "bluetooth"],
        "update_blue_5": ["data", "bluetooth"],
        "update_blue_6": ["data", "bluetooth"],
        "update_blue_7": ["data", "bluetooth"],
        "update_blue_8": ["data", "bluetooth"],
        "update_blue_9": ["data", "bluetooth"],
        "update_blue_a": ["data", "bluetooth"],
        "update_blue_b": ["data", "bluetooth"],
        "update_blue_c": ["data", "bluetooth"],
        "update_blue_d": ["data", "bluetooth"],
        "update_blue_e": ["data", "bluetooth"],
        "update_blue_f": ["data", "bluetooth"],
        "update_cell_gsm": ["data", "cell"],
        "update_cell_lte": ["data", "cell"],
        "update_cell_wcdma": ["data", "cell"],
        "update_cellarea": ["data", "cellarea"],
        "update_datamap_ne": ["data", "datamap"],
        "update_datamap_nw": ["data", "datamap"],
        "update_datamap_se": ["data", "datamap"],
        "update_datamap_sw": ["data", "datamap"],
        "update_incoming": ["data", "report"],
        "update_wifi_0": ["data", "wifi"],
        "update_wifi_1": ["data", "wifi"],
        "update_wifi_2": ["data", "wifi"],
        "update_wifi_3": ["data", "wifi"],
        "update_wifi_4": ["data", "wifi"],
        "update_wifi_5": ["data", "wifi"],
        "update_wifi_6": ["data", "wifi"],
        "update_wifi_7": ["data", "wifi"],
        "update_wifi_8": ["data", "wifi"],
        "update_wifi_9": ["data", "wifi"],
        "update_wifi_a": ["data", "wifi"],
        "update_wifi_b": ["data", "wifi"],
        "update_wifi_c": ["data", "wifi"],
        "update_wifi_d": ["data", "wifi"],
        "update_wifi_e": ["data", "wifi"],
        "update_wifi_f": ["data", "wifi"],
    }

    def test_empty_queues(self, celery, redis, metricsmock):
        monitor_queue_size.delay().get()
        for name in celery.all_queues:
            spec = self.expected_queues[name]
            expected_tags = [f"queue:{name}", f"queue_type:{spec[0]}"]
            if spec[0] == "data":
                expected_tags.append(f"data_type:{spec[1]}")
            metricsmock.assert_gauge_once("queue", value=0, tags=expected_tags)

    def test_nonempty(self, celery, redis, metricsmock):
        data = {}
        for name in celery.all_queues:
            data[name] = random.randint(1, 10)

        for key, val in data.items():
            redis.lpush(key, *range(val))

        monitor_queue_size.delay().get()
        for key, val in data.items():
            spec = self.expected_queues[key]
            expected_tags = [f"queue:{key}", f"queue_type:{spec[0]}"]
            if spec[0] == "data":
                expected_tags.append(f"data_type:{spec[1]}")
            metricsmock.assert_gauge_once("queue", value=val, tags=expected_tags)


class TestSentryTest:
    def test_basic(self, celery, raven_client):
        sentry_test.delay(msg="test message")
        msgs = [item["message"] for item in raven_client.msgs]
        assert msgs == ["test message"]

        raven_client._clear()
