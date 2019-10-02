"""Functionality related to statsd, sentry and freeform logging."""
from collections import deque
import logging
import logging.config
import time

from pyramid.httpexceptions import HTTPException, HTTPClientError, HTTPRedirection
from raven import Client as RavenClient
from raven.transport.gevent import GeventedHTTPTransport
from raven.transport.http import HTTPTransport
from raven.transport.threaded import ThreadedHTTPTransport
from datadog.dogstatsd.base import DogStatsd

from ichnaea.conf import settings
from ichnaea.exceptions import BaseClientError
from ichnaea.util import version_info


def configure_logging():
    """Configure Python logging."""
    local_dev_env = settings("local_dev_env")

    if local_dev_env:
        level = "DEBUG"
        celery_level = "INFO"
        handlers = ["console"]
    else:
        level = "INFO"
        celery_level = "WARNING"
        handlers = ["mozlog"]

    logging_config = {
        "version": 1,
        "disable_existing_loggers": True,
        "formatters": {
            "app": {"format": "%(asctime)s %(levelname)-5s [%(name)s] - %(message)s"},
            "json": {
                "()": "dockerflow.logging.JsonLogFormatter",
                "logger_name": "ichnaea",
            },
        },
        "handlers": {
            "console": {
                "class": "logging.StreamHandler",
                "formatter": "app",
                "level": "DEBUG",
            },
            "mozlog": {
                "class": "logging.StreamHandler",
                "formatter": "json",
                "level": "DEBUG",
            },
        },
        "loggers": {
            "alembic": {"propagate": False, "handlers": handlers, "level": level},
            "celery": {"propagate": False, "handlers": handlers, "level": celery_level},
            "ichnaea": {"propagate": False, "handlers": handlers, "level": level},
        },
        "root": {"handlers": handlers, "level": "WARNING"},
    }

    logging.config.dictConfig(logging_config)


RAVEN_TRANSPORTS = {
    "gevent": GeventedHTTPTransport,
    "sync": HTTPTransport,
    "threaded": ThreadedHTTPTransport,
}


def configure_raven(transport=None, _client=None):
    """
    Configure and return a :class:`raven.Client` instance.

    :param transport: The transport to use, one of the
                      :data:`RAVEN_TRANSPORTS` keys.
    :param _client: Test-only hook to provide a pre-configured client.
    """
    if _client is not None:
        return _client

    transport = RAVEN_TRANSPORTS.get(transport)
    if not transport:
        raise ValueError("No valid raven transport was configured.")

    dsn = settings("sentry_dsn")
    klass = DebugRavenClient if not dsn else RavenClient
    release = version_info()["tag"]
    client = klass(dsn=dsn, transport=transport, release=release)
    return client


def configure_stats(_client=None):
    """
    Configure and return a :class:`~ichnaea.log.StatsClient` instance.

    :param _client: Test-only hook to provide a pre-configured client.
    """
    if _client is not None:
        return _client

    statsd_host = settings("statsd_host")
    klass = DebugStatsClient if not statsd_host else StatsClient
    namespace = None if settings("testing") else "location"
    client = klass(host=statsd_host, port=8125, namespace=namespace, use_ms=True)
    return client


def log_tween_factory(handler, registry):
    """A logging tween, doing automatic statsd and raven collection."""

    def log_tween(request):
        if request.path in registry.skip_logging or request.path.startswith("/static"):
            # shortcut handling for static assets
            try:
                return handler(request)
            except HTTPException:
                # don't capture exceptions for normal responses
                raise
            except Exception:
                registry.raven_client.captureException()
                raise

        stats_client = registry.stats_client
        start = time.time()
        statsd_tags = [
            # Convert a URI to a statsd acceptable metric name
            "path:%s" % request.path.replace("/", ".").lstrip(".").replace("@", "-"),
            "method:%s" % request.method.lower(),
        ]

        def timer_send():
            duration = int(round((time.time() - start) * 1000))
            stats_client.timing("request", duration, tags=statsd_tags)

        def counter_send(status_code):
            stats_client.incr("request", tags=statsd_tags + ["status:%s" % status_code])

        try:
            response = handler(request)
            timer_send()
            counter_send(response.status_code)
            return response
        except (BaseClientError, HTTPRedirection) as exc:
            # don't capture exceptions
            timer_send()
            counter_send(exc.status_code)
            raise
        except HTTPClientError:
            # ignore general client side errors
            raise
        except Exception as exc:
            timer_send()
            if isinstance(exc, HTTPException):
                status = exc.status_code
            else:
                status = 500
            counter_send(status)
            registry.raven_client.captureException()
            raise

    return log_tween


class DebugRavenClient(RavenClient):
    """An in-memory raven client with an inspectable message queue."""

    def __init__(self, *args, **kw):
        super(DebugRavenClient, self).__init__(*args, **kw)
        self.msgs = deque(maxlen=100)

    def _clear(self):
        self.msgs.clear()
        self.context.clear()

    def is_enabled(self):
        return True

    def send(self, auth_header=None, **data):
        self.msgs.append(data)
        self._successful_send()

    def check(self, expected=()):
        """
        Checks the raven message stream looking for the expected messages.

        The expected argument should be a list of either names or tuples.

        If it is a tuple, it should be a tuple of name and an expected count.

        The names are matched via startswith against the captured exception
        messages.
        """
        messages = [msg["message"] for msg in self.msgs]
        matched_msgs = []
        for exp in expected:
            count = 1
            name = exp
            if isinstance(exp, tuple):
                name, count = exp
            matches = [msg for msg in self.msgs if msg["message"].startswith(name)]
            matched_msgs.extend(matches)
            assert len(matches) == count, messages

        for msg in matched_msgs:
            self.msgs.remove(msg)


class StatsClient(DogStatsd):
    """A statsd client."""

    def close(self):
        if self.socket:
            self.socket.close()
            self.socket = None

    def incr(self, *args, **kw):
        return self.increment(*args, **kw)


class DebugStatsClient(StatsClient):
    """An in-memory statsd client with an inspectable message queue."""

    def __init__(self, *args, **kw):
        super(DebugStatsClient, self).__init__(*args, **kw)
        self.msgs = deque(maxlen=100)

    def _clear(self):
        self.msgs.clear()

    def _send_to_server(self, packet):
        self.msgs.append(packet)

    def _find_messages(self, msg_type, msg_name, msg_value=None, msg_tags=()):
        data = {
            "counter": [],
            "timer": [],
            "gauge": [],
            "histogram": [],
            "meter": [],
            "set": [],
        }
        for msg in self.msgs:
            tags = ()
            if "|#" in msg:
                parts = msg.split("|#")
                tags = parts[-1].split(",")
                msg = parts[0]
            suffix = msg.split("|")[-1]
            name, value = msg.split("|")[0].split(":")
            value = int(value)
            if suffix == "g":
                data["gauge"].append((name, value, tags))
            elif suffix == "ms":
                data["timer"].append((name, value, tags))
            elif suffix.startswith("c"):
                data["counter"].append((name, value, tags))
            elif suffix == "h":
                data["histogram"].append((name, value, tags))
            elif suffix == "m":
                data["meter"].append((name, value, tags))
            elif suffix == "s":
                data["set"].append((name, value, tags))

        result = []
        for msg in data.get(msg_type):
            if msg[0] == msg_name:
                if msg_value is None or msg[1] == msg_value:
                    if not msg_tags or msg[2] == msg_tags:
                        result.append((msg[0], msg[1], msg[2]))
        return result

    def check(self, total=None, **kw):
        """
        Checks a partial specification of messages to be found in
        the stats message stream.
        """
        if total is not None:
            assert total == len(self.msgs)

        for (msg_type, preds) in kw.items():
            for pred in preds:
                match = 1
                value = None
                tags = ()
                if isinstance(pred, str):
                    name = pred
                elif isinstance(pred, tuple):
                    if len(pred) == 2:
                        (name, match) = pred
                        if isinstance(match, list):
                            tags = match
                            match = 1
                    elif len(pred) == 3:
                        (name, match, value) = pred
                        if isinstance(value, list):
                            tags = value
                            value = None
                    elif len(pred) == 4:
                        (name, match, value, tags) = pred
                    else:
                        raise TypeError("wanted 2, 3 or 4 tuple, got %s" % type(pred))
                else:
                    raise TypeError("wanted str or tuple, got %s" % type(pred))
                msgs = self._find_messages(msg_type, name, value, tags)
                if isinstance(match, int):
                    assert match == len(msgs)
