from collections import defaultdict
from datetime import timedelta
import json
import logging

import markus
from simple_pid import PID

from ichnaea import util

METRICS = markus.get_metrics()
LOGGER = logging.getLogger(__name__)


class ApiKeyLimits:
    def __init__(self, task):
        self.task = task

    def __call__(self):
        today = util.utcnow().strftime("%Y%m%d")
        keys = self.task.redis_client.keys("apilimit:*:" + today)
        values = []
        if keys:
            values = self.task.redis_client.mget(keys)
            keys = [k.decode("utf-8").split(":")[1:3] for k in keys]

        for (api_key, path), value in zip(keys, values):
            METRICS.gauge(
                "api.limit", value=int(value), tags=["key:" + api_key, "path:" + path]
            )


class ApiUsers:
    def __init__(self, task):
        self.task = task

    def __call__(self):
        days = {}
        today = util.utcnow().date()
        for i in range(0, 7):
            day = today - timedelta(days=i)
            days[i] = day.strftime("%Y-%m-%d")

        metrics = defaultdict(list)
        for key in self.task.redis_client.scan_iter(match="apiuser:*", count=100):
            _, api_type, api_name, day = key.decode("ascii").split(":")
            if day not in days.values():
                # delete older entries
                self.task.redis_client.delete(key)
                continue

            if day == days[0]:
                metrics[(api_type, api_name, "1d")].append(key)

            metrics[(api_type, api_name, "7d")].append(key)

        for parts, keys in metrics.items():
            api_type, api_name, interval = parts
            value = self.task.redis_client.pfcount(*keys)

            METRICS.gauge(
                "%s.user" % api_type,
                value=value,
                tags=["key:%s" % api_name, "interval:%s" % interval],
            )


class QueueSizeAndRateControl:
    """Generate gauge metrics for queue sizes, and tune sample rate.

    This covers the celery task queues and the data queues.

    There are dynamically created export queues, with names like
    "export_queue_internal", or maybe "queue_export_internal", which are no
    longer monitored. See ichnaea/models/config.py for queue generation.

    The station data queues represent the backlog, and the rate controller,
    if enabled, attempts to keep the backlog size near a target size by
    adjusting the global locate sample rate.
    """

    def __init__(self, task):
        self.task = task
        self.rate = 0
        self.rc_enabled = None
        self.rc_target = None
        self.rc_kp = None
        self.rc_ki = None
        self.rc_kd = None
        self.rc_state = None
        self.rc_controller = None

    def __call__(self):
        # Gather queue lengths, rate control settings from Redis
        names = list(self.task.app.all_queues.keys())
        with self.task.redis_client.pipeline() as pipe:
            for name in names:
                pipe.llen(name)
            queue_lengths = pipe.execute()
        self.load_rc_params()

        # Emit queue metrics and calculate the station backlog
        backlog = 0
        for name, value in zip(names, queue_lengths):
            tags_list = ["queue:" + name]
            for tag_name, tag_val in self.task.app.all_queues[name].items():
                tags_list.append(f"{tag_name}:{tag_val}")
                if tag_name == "data_type" and tag_val in ("bluetooth", "cell", "wifi"):
                    backlog += value
            METRICS.gauge("queue", value, tags=tags_list)

        # Use the rate controller to update the global rate
        if self.rc_enabled:
            self.run_rate_controller(backlog)
            rc_state = self.freeze_controller_state()
            with self.task.redis_client.pipeline() as pipe:
                pipe.set("global_locate_sample_rate", self.rate)
                pipe.set("rate_controller_state", rc_state)
                pipe.execute()
            METRICS.gauge("rate_control.locate.target", self.rc_target)
            METRICS.gauge("rate_control.locate.kp", self.rc_kp)
            METRICS.gauge("rate_control.locate.ki", self.rc_ki)
            METRICS.gauge("rate_control.locate.kd", self.rc_kd)

            p_term, i_term, d_term = self.rc_controller.components
            METRICS.gauge("rate_control.locate.p_term", p_term)
            METRICS.gauge("rate_control.locate.i_term", i_term)
            METRICS.gauge("rate_control.locate.d_term", d_term)

        # Emit the current (controlled or manual) global rate
        METRICS.gauge("rate_control.locate", self.rate)

    def load_rc_params(self):
        """Load rate controller parameters from Redis-stored strings."""
        with self.task.redis_client.pipeline() as pipe:
            pipe.get("global_locate_sample_rate")
            pipe.get("rate_controller_enabled")
            pipe.get("rate_controller_target")
            pipe.get("rate_controller_kp")
            pipe.get("rate_controller_ki")
            pipe.get("rate_controller_kd")
            pipe.get("rate_controller_state")
            rate, rc_enabled, rc_target, rc_kp, rc_ki, rc_kd, rc_state = pipe.execute()

        try:
            self.rate = float(rate)
        except (TypeError, ValueError):
            self.rate = 100.0

        def load_param(param_type, name, raw_value, range_check):
            """
            Load and validate a parameter

            Reset invalid parameters in Redis
            Returns (value, is_valid)
            """
            try:
                val = param_type(raw_value)
                if not range_check(val):
                    raise ValueError("out of range")
                return val, True
            except (TypeError, ValueError):
                log_fmt = "Redis key '%s' has invalid value %r, disabling rate control."
                LOGGER.warning(log_fmt, name, raw_value)
                self.task.redis_client.set(name, 0)
                return None, False

        # Validate rate_controller_enabled, exit early if disabled
        self.rc_enabled, valid = load_param(
            int, "rate_controller_enabled", rc_enabled, lambda x: x in (0, 1)
        )
        if not self.rc_enabled:
            self.task.redis_client.set("rate_controller_state", "{}")
            return

        # Validate simple PID parameters, exit if any are invalid
        valid = [True] * 4
        self.rc_target, valid[0] = load_param(
            int, "rate_controller_target", rc_target, lambda x: x >= 0
        )
        self.rc_kp, valid[1] = load_param(
            float, "rate_controller_kp", rc_kp, lambda x: x >= 0
        )
        self.rc_ki, valid[2] = load_param(
            float, "rate_controller_ki", rc_ki, lambda x: x >= 0
        )
        self.rc_kd, valid[3] = load_param(
            float, "rate_controller_kd", rc_kd, lambda x: x >= 0
        )
        if not all(valid):
            self.task.redis_client.set("rate_controller_enabled", 0)
            self.task.redis_client.set("rate_controller_state", "{}")
            self.rc_enabled = False
            return

        # State is None if new, or a JSON-encoded string
        try:
            self.rc_state = json.loads(rc_state.decode("utf8"))
        except AttributeError:
            self.rc_state = {}

        self.rc_controller = PID(
            self.rc_kp,
            self.rc_ki,
            self.rc_kd,
            self.rc_target,
            sample_time=None,
            output_limits=(0, self.rc_target),
        )
        if self.rc_state.get("state") == "running":
            # Update controller with previous state
            try:
                p_term = self.rc_state["p_term"]
                i_term = self.rc_state["i_term"]
                d_term = self.rc_state["d_term"]
                last_input = self.rc_state["last_input"]
                last_output = self.rc_state["last_output"]
                last_time = self.rc_state["last_time"]
            except KeyError:
                # Skip loading state, start with fresh controller
                return

            self.rc_controller._proportional = p_term
            self.rc_controller._integral = i_term
            self.rc_controller._derivative = d_term
            self.rc_controller._last_input = last_input
            self.rc_controller._last_output = last_output
            self.rc_controller._last_time = last_time

            # Apply limits, which may clamp integral and last output
            self.rc_controller.output_limits = (0, self.rc_target)

    def run_rate_controller(self, backlog):
        """Generate a new sample rate."""
        if not (self.rc_enabled or self.rc_controller or self.rc_state):
            return

        output = self.rc_controller(backlog)
        self.rate = 100.0 * max(0.0, min(1.0, output / self.rc_target))

    def freeze_controller_state(self):
        """Convert a PID controller to a JSON encoded string."""
        if self.rc_controller:
            p_term, i_term, d_term = self.rc_controller.components
            state = {
                "state": "running",
                "p_term": p_term,
                "i_term": i_term,
                "d_term": d_term,
                "last_output": self.rc_controller._last_output,
                "last_input": self.rc_controller._last_input,
                "last_time": self.rc_controller._last_time,
            }
        else:
            state = {"state": "new"}
        return json.dumps(state)
