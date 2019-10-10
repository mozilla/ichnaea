"""Functionality related to statsd, sentry and freeform logging."""
from collections import deque
import logging
import logging.config
import time

import markus
from pyramid.httpexceptions import HTTPException, HTTPClientError, HTTPRedirection
from raven import Client as RavenClient
from raven.transport.gevent import GeventedHTTPTransport
from raven.transport.http import HTTPTransport
from raven.transport.threaded import ThreadedHTTPTransport

from ichnaea.conf import settings
from ichnaea.exceptions import BaseClientError
from ichnaea.util import version_info


METRICS = markus.get_metrics()


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
            "markus": {"propagate": False, "handlers": handlers, "level": level},
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
    """Configure and return a :class:`raven.Client` instance.

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


def configure_stats():
    """Configure Markus for metrics."""
    local_dev_env = settings("local_dev_env")
    if local_dev_env:
        markus.configure(backends=[{"class": "markus.backends.logging.LoggingMetrics"}])
        return

    if settings("statsd_host"):
        markus.configure(
            backends=[
                {
                    "class": "markus.backends.datadog.DatadogMetrics",
                    "options": {
                        "statsd_host": settings("statsd_host"),
                        "statsd_port": settings("statsd_port"),
                        "statsd_namespace": "location",
                    },
                }
            ]
        )
    else:
        logging.getLogger(__name__).warning("STATSD_HOST not set; no statsd configured")


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

        start = time.time()
        statsd_tags = [
            # Convert a URI to a statsd acceptable metric name
            "path:%s" % request.path.replace("/", ".").lstrip(".").replace("@", "-"),
            "method:%s" % request.method.lower(),
        ]

        def timer_send():
            duration = int(round((time.time() - start) * 1000))
            METRICS.timing("request", duration, tags=statsd_tags)

        def counter_send(status_code):
            METRICS.incr("request", tags=statsd_tags + ["status:%s" % status_code])

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
