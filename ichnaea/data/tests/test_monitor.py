from datetime import timedelta
import json
import random
import time

import pytest

from ichnaea.data.tasks import (
    monitor_api_key_limits,
    monitor_api_users,
    monitor_queue_size_and_rate_control,
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


class TestMonitorQueueSizeAndRateControl:
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
        monitor_queue_size_and_rate_control.delay().get()
        for name in celery.all_queues:
            spec = self.expected_queues[name]
            expected_tags = [f"queue:{name}", f"queue_type:{spec[0]}"]
            if spec[0] == "data":
                expected_tags.append(f"data_type:{spec[1]}")
            metricsmock.assert_gauge_once("queue", value=0, tags=expected_tags)
        metricsmock.assert_gauge_once("rate_control.locate", value=100.0)

    def test_nonempty(self, celery, redis, metricsmock):
        data = {}
        for name in celery.all_queues:
            data[name] = random.randint(1, 10)

        for key, val in data.items():
            redis.lpush(key, *range(val))

        monitor_queue_size_and_rate_control.delay().get()
        for key, val in data.items():
            spec = self.expected_queues[key]
            expected_tags = [f"queue:{key}", f"queue_type:{spec[0]}"]
            if spec[0] == "data":
                expected_tags.append(f"data_type:{spec[1]}")
            metricsmock.assert_gauge_once("queue", value=val, tags=expected_tags)
        metricsmock.assert_gauge_once("rate_control.locate", value=100.0)

    def test_rate_control(self, celery, redis, metricsmock):
        redis.set("rate_controller_kp", 1.0)
        redis.set("rate_controller_ki", 0.002)
        redis.set("rate_controller_kd", 0.2)
        redis.set("rate_controller_target", 1000)
        redis.set("rate_controller_enabled", 1)

        monitor_queue_size_and_rate_control.delay().get()

        assert int(redis.get("rate_controller_enabled")) == 1
        assert float(redis.get("global_locate_sample_rate")) == 100.0

        raw_state = redis.get("rate_controller_state")
        assert raw_state
        state = json.loads(raw_state.decode("utf8"))
        assert state == {
            "state": "running",
            "p_term": 1000.0,
            "i_term": state["i_term"],
            "d_term": -0.0,
            "last_input": 0,
            "last_output": 1000,
            "last_time": state["last_time"],
        }

        metricsmock.assert_gauge_once("rate_control.locate.target", value=1000)
        metricsmock.assert_gauge_once("rate_control.locate.kp", value=1)
        metricsmock.assert_gauge_once("rate_control.locate.ki", value=0.002)
        metricsmock.assert_gauge_once("rate_control.locate.kd", value=0.2)
        metricsmock.assert_gauge_once("rate_control.locate.p_term", value=1000)
        metricsmock.assert_gauge_once(
            "rate_control.locate.i_term", value=state["i_term"]
        )
        metricsmock.assert_gauge_once(
            "rate_control.locate.d_term", value=state["d_term"]
        )
        metricsmock.assert_gauge_once("rate_control.locate", value=100.0)

    @pytest.mark.parametrize(
        "key",
        (
            "rate_controller_enabled",
            "rate_controller_target",
        ),
    )
    @pytest.mark.parametrize("value", (None, -1, "a string"))
    def test_rate_control_auto_disable(self, celery, redis, metricsmock, key, value):
        """When some Redis values fail to validate, it disables the rate controller."""
        # TODO: check log entry when switched to structlog
        rc_params = {
            "rate_controller_target": 1000,
            "rate_controller_kp": 1,
            "rate_controller_ki": 0.002,
            "rate_controller_kd": 0.2,
            "rate_controller_enabled": 1,
        }
        rc_params[key] = value
        for name, init in rc_params.items():
            if init is not None:
                redis.set(name, init)

        monitor_queue_size_and_rate_control.delay().get()

        assert int(redis.get("rate_controller_enabled")) == 0
        assert int(redis.get(key)) == 0
        raw_state = redis.get("rate_controller_state")
        assert raw_state
        assert raw_state.decode("utf8") == "{}"
        metricsmock.assert_gauge_once("rate_control.locate", value=100.0)

    @pytest.mark.parametrize(
        "key, default",
        (
            ("rate_controller_kp", 8),
            ("rate_controller_ki", 0),
            ("rate_controller_kd", 0),
        ),
    )
    @pytest.mark.parametrize("value", (None, -1, "a string"))
    def test_rate_control_auto_default(
        self, celery, redis, metricsmock, key, default, value
    ):
        """Some Redis values are initialized to defaults."""
        # TODO: check log entry when switched to structlog
        rc_params = {
            "rate_controller_target": 1000,
            "rate_controller_kp": 1,
            "rate_controller_ki": 0.002,
            "rate_controller_kd": 0.2,
            "rate_controller_enabled": 1,
        }
        rc_params[key] = value
        for name, init in rc_params.items():
            if init is not None:
                redis.set(name, init)

        monitor_queue_size_and_rate_control.delay().get()
        assert int(redis.get(key)) == default
        raw_state = redis.get("rate_controller_state")
        assert raw_state
        if value is None:
            # Set to default and loaded
            assert int(redis.get("rate_controller_enabled")) == 1
            assert json.loads(raw_state)
        else:
            # Set to 0 and disabled
            assert int(redis.get("rate_controller_enabled")) == 0
            metricsmock.assert_gauge_once("rate_control.locate", value=100.0)
            assert raw_state.decode("utf8") == "{}"

    def test_rate_control_reload(self, celery, redis):
        redis.set("rate_controller_kp", 1.0)
        redis.set("rate_controller_ki", 0.002)
        redis.set("rate_controller_kd", 0.2)
        redis.set("rate_controller_target", 1000)
        redis.set("rate_controller_enabled", 1)
        redis.lpush("update_wifi_b", *range(10))
        old_state = {
            "state": "running",
            "p_term": 1000,
            "i_term": 0.0001,
            "d_term": 0.0,
            "last_input": 0,
            "last_output": 1000,
            "last_time": time.monotonic() - 60.0,
        }
        redis.set("rate_controller_state", json.dumps(old_state))

        monitor_queue_size_and_rate_control.delay().get()

        assert int(redis.get("rate_controller_enabled")) == 1

        # Backlog is well below target, sample rate is 100%
        assert float(redis.get("global_locate_sample_rate")) == 100.0

        raw_state = redis.get("rate_controller_state")
        assert raw_state
        state = json.loads(raw_state.decode("utf8"))
        assert state == {
            "state": "running",
            "p_term": 990.0,
            "i_term": state["i_term"],
            "d_term": state["d_term"],
            "last_input": 10,
            "last_output": 1000,
            "last_time": state["last_time"],
        }
        assert state["i_term"] != old_state["i_term"]
        assert state["d_term"] != old_state["d_term"]
        assert state["last_time"] > old_state["last_time"]

    def test_rate_control_new_setpoint(self, celery, redis):
        redis.set("rate_controller_kp", 1.0)
        redis.set("rate_controller_ki", 0.002)
        redis.set("rate_controller_kd", 0.2)
        redis.set("rate_controller_target", 5)  # 1000 to 5
        redis.set("rate_controller_enabled", 1)
        redis.lpush("update_wifi_b", *range(10))
        old_state = {
            "state": "running",
            "p_term": 990.0,
            "i_term": 0.0001,
            "d_term": 0.0,
            "last_input": 10,
            "last_output": 1000,
            "last_time": time.monotonic() - 60.0,
        }
        redis.set("rate_controller_state", json.dumps(old_state))

        monitor_queue_size_and_rate_control.delay().get()

        assert int(redis.get("rate_controller_enabled")) == 1
        # Queue size is now well above target, sample rate is 0%
        assert float(redis.get("global_locate_sample_rate")) == 0.0

        raw_state = redis.get("rate_controller_state")
        assert raw_state
        state = json.loads(raw_state.decode("utf8"))
        assert state == {
            "state": "running",
            "p_term": -5.0,
            "i_term": state["i_term"],
            "d_term": state["d_term"],
            "last_input": 10,
            "last_output": 0,
            "last_time": state["last_time"],
        }
        assert state["i_term"] != old_state["i_term"]
        assert state["last_time"] > old_state["last_time"]

    def test_rate_control_invalid_state(self, celery, redis):
        redis.set("rate_controller_kp", 1.0)
        redis.set("rate_controller_ki", 0.002)
        redis.set("rate_controller_kd", 0.2)
        redis.set("rate_controller_target", 9)
        redis.set("rate_controller_enabled", 1)
        redis.lpush("update_wifi_b", *range(10))
        old_state = {
            "state": "running",
            "p_term": 990.0,
            "i_term": 0.0001,
            "d_term": 0.0,
            "last_input": 10,
            "last_output": 100,
            # Missing last_time
        }
        redis.set("rate_controller_state", json.dumps(old_state))

        monitor_queue_size_and_rate_control.delay().get()

        assert int(redis.get("rate_controller_enabled")) == 1
        # Queue size is above target, sample rate is 0%
        assert float(redis.get("global_locate_sample_rate")) == 0.0

        raw_state = redis.get("rate_controller_state")
        assert raw_state
        state = json.loads(raw_state.decode("utf8"))
        assert state == {
            "state": "running",
            "p_term": -1.0,
            "i_term": 0,
            "d_term": -0.0,
            "last_input": 10,
            "last_output": 0,
            "last_time": state["last_time"],
        }
        assert state["i_term"] != old_state["i_term"]


class TestSentryTest:
    def test_basic(self, celery, raven_client):
        sentry_test.delay(msg="test message")
        msgs = [item["message"] for item in raven_client.msgs]
        assert msgs == ["test message"]

        raven_client._clear()
