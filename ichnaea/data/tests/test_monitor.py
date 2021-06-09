from datetime import timedelta
import json
import random
import time
from unittest import mock

import pytest
from sqlalchemy.exc import OperationalError

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


@pytest.fixture
def monitor_session():
    """Mock the database session for MonitorQueueSizeAndRateControl"""
    mock_session = mock.Mock(spec_set=("scalar",))
    mock_session.scalar.return_value = 123
    mock_transaction = mock.Mock(spec_set=("__enter__", "__exit__"))
    mock_transaction.__enter__ = mock.Mock(return_value=mock_session)
    mock_transaction.__exit__ = mock.Mock(return_value=False)
    with mock.patch.object(
        monitor_queue_size_and_rate_control, "db_session", return_value=mock_transaction
    ):
        yield mock_session


@pytest.fixture
def monitor_redis(redis):
    """Setup the rate controller for MonitorQueueSizeAndRateControl"""
    with redis.pipeline() as pipe:
        pipe.set("rate_controller_kp", 1.0)
        pipe.set("rate_controller_ki", 0.002)
        pipe.set("rate_controller_kd", 0.2)
        pipe.set("rate_controller_target", 1000)
        pipe.set("rate_controller_enabled", 1)
        pipe.set("rate_controller_trx_purging", 0)
        pipe.set("rate_controller_trx_min", 1000)
        pipe.set("rate_controller_trx_max", 1000000)
        pipe.execute()
    return redis


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
        """Empty queues emit metrics and have a rate of 100%"""
        monitor_queue_size_and_rate_control.delay().get()
        for name in celery.all_queues:
            spec = self.expected_queues[name]
            expected_tags = [f"queue:{name}", f"queue_type:{spec[0]}"]
            if spec[0] == "data":
                expected_tags.append(f"data_type:{spec[1]}")
            metricsmock.assert_gauge_once("queue", value=0, tags=expected_tags)
        metricsmock.assert_gauge_once("rate_control.locate", value=100.0)

    def test_nonempty(self, celery, redis, metricsmock):
        """Non-empty but low queues emit metrics, have a rate of 100%"""
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

    def test_rate_control(self, celery, monitor_redis, monitor_session, metricsmock):
        """Rate controller runs and emits metrics when enabled."""
        redis = monitor_redis
        monitor_queue_size_and_rate_control.delay().get()

        assert int(redis.get("rate_controller_enabled")) == 1
        assert int(redis.get("rate_controller_trx_purging")) == 0
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
        metricsmock.assert_gauge_once("rate_control.locate.pterm", value=1000)
        metricsmock.assert_gauge_once(
            "rate_control.locate.iterm", value=state["i_term"]
        )
        metricsmock.assert_gauge_once(
            "rate_control.locate.dterm", value=state["d_term"]
        )
        metricsmock.assert_gauge_once("rate_control.locate", value=100.0)
        metricsmock.assert_gauge_once("trx_history.length", value=123)
        metricsmock.assert_gauge_once("trx_history.min", value=1000)
        metricsmock.assert_gauge_once("trx_history.max", value=1000000)
        metricsmock.assert_gauge_once("trx_history.purging", value=0)

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

    def test_trx_history_metric(self, metricsmock, monitor_session, monitor_redis):
        """The MySQL transaxtion history length is converted to a metric."""
        monitor_queue_size_and_rate_control.delay().get()

        monitor_session.scalar.assert_called_once_with(
            "SELECT count FROM information_schema.innodb_metrics"
            " WHERE name = 'trx_rseg_history_len';"
        )
        metricsmock.assert_gauge_once("trx_history.length", value=123)
        metricsmock.assert_gauge_once("trx_history.min", 1000)
        metricsmock.assert_gauge_once("trx_history.max", 1000000)
        metricsmock.assert_gauge_once("trx_history.purging", 0)

    def test_trx_history_not_allowed(self, metricsmock, monitor_redis, monitor_session):
        """If MySQL connection does not have PROCESS privilege, then do not send metric."""
        monitor_session.scalar.side_effect = OperationalError(
            statement="SELECT count FROM information_schema...",
            params=[],
            orig=Exception(1227),
        )
        monitor_queue_size_and_rate_control.delay().get()

        monitor_session.scalar.assert_called_once()
        metricsmock.assert_not_gauge("trx_history.length")
        metricsmock.assert_not_gauge("trx_history.min")
        metricsmock.assert_not_gauge("trx_history.max")
        metricsmock.assert_not_gauge("trx_history.purging")

    def test_trx_history_other_error_raised(
        self, metricsmock, monitor_session, raven_client
    ):
        """If a different error is raised, the task raises the exception."""
        monitor_session.scalar.side_effect = OperationalError(
            statement="SELECT count FROM information_schema...",
            params=[],
            orig=Exception(1234),
        )
        with pytest.raises(OperationalError):
            monitor_queue_size_and_rate_control.delay().get()

        monitor_session.scalar.assert_called_once()
        metricsmock.assert_not_gauge("trx_history.length", value=123)
        assert len(raven_client.msgs) == 1
        raven_client._clear()

    def test_trx_history_override(
        self, celery, monitor_redis, monitor_session, metricsmock
    ):
        """The rate controller enters purging mode above max transaction history."""
        monitor_redis.set("rate_controller_trx_min", 10)
        monitor_redis.set("rate_controller_trx_max", 100)
        monitor_redis.set("rate_controller_trx_purging", 0)
        monitor_redis.set("global_locate_sample_rate", 100)

        monitor_queue_size_and_rate_control.delay().get()

        assert float(monitor_redis.get("global_locate_sample_rate")) == 0.0
        assert int(monitor_redis.get("rate_controller_trx_purging")) == 1
        metricsmock.assert_gauge_once("trx_history.length", value=123)
        metricsmock.assert_gauge_once("trx_history.min", value=10)
        metricsmock.assert_gauge_once("trx_history.max", value=100)
        metricsmock.assert_gauge_once("trx_history.purging", value=1)

    def test_trx_history_purging(
        self, celery, monitor_redis, monitor_session, metricsmock
    ):
        """The rate controller remains in purging mode above min transaction history."""
        monitor_redis.set("rate_controller_trx_min", 10)
        monitor_redis.set("rate_controller_trx_max", 200)
        monitor_redis.set("rate_controller_trx_purging", 1)
        monitor_redis.set("global_locate_sample_rate", 1)

        monitor_queue_size_and_rate_control.delay().get()

        assert float(monitor_redis.get("global_locate_sample_rate")) == 0.0
        assert int(monitor_redis.get("rate_controller_trx_purging")) == 1
        metricsmock.assert_gauge_once("trx_history.length", value=123)
        metricsmock.assert_gauge_once("trx_history.min", value=10)
        metricsmock.assert_gauge_once("trx_history.max", value=200)
        metricsmock.assert_gauge_once("trx_history.purging", value=1)

    def test_trx_history_complete(
        self, celery, monitor_redis, monitor_session, metricsmock
    ):
        """The rate controller exits purging mode below min transaction history."""
        monitor_redis.set("rate_controller_trx_min", 124)
        monitor_redis.set("rate_controller_trx_max", 200)
        monitor_redis.set("rate_controller_trx_purging", 1)
        monitor_redis.set("global_locate_sample_rate", 0)

        monitor_queue_size_and_rate_control.delay().get()

        assert float(monitor_redis.get("global_locate_sample_rate")) == 100.0
        assert int(monitor_redis.get("rate_controller_trx_purging")) == 0
        metricsmock.assert_gauge_once("trx_history.length", value=123)
        metricsmock.assert_gauge_once("trx_history.min", value=124)
        metricsmock.assert_gauge_once("trx_history.max", value=200)
        metricsmock.assert_gauge_once("trx_history.purging", value=0)

    def test_emit_metrics_rc_disabled(
        self, celery, monitor_redis, monitor_session, metricsmock
    ):
        """Metrics are emitted even when the rate controller is disabled."""
        monitor_redis.set("rate_controller_enabled", 0)
        monitor_redis.set("global_locate_sample_rate", "56.4")

        monitor_queue_size_and_rate_control.delay().get()

        assert monitor_redis.get("global_locate_sample_rate") == b"56.4"
        metricsmock.assert_gauge_once("trx_history.length", value=123)
        metricsmock.assert_gauge_once("rate_control.locate", value=56.4)
        metricsmock.assert_not_gauge("trx_history.purging")
        metricsmock.assert_not_gauge("rate_control.locate.target")


class TestSentryTest:
    def test_basic(self, celery, raven_client):
        sentry_test.delay(msg="test message")
        msgs = [item["message"] for item in raven_client.msgs]
        assert msgs == ["test message"]

        raven_client._clear()
