"""Functionality related to statsd, sentry and freeform logging."""
from collections import deque
import logging
import logging.config
import time

import markus
from markus.utils import generate_tag
from pyramid.httpexceptions import HTTPException, HTTPClientError, HTTPRedirection
from raven import Client as RavenClient
from raven.transport.gevent import GeventedHTTPTransport
from raven.transport.http import HTTPTransport
from raven.transport.threaded import ThreadedHTTPTransport
import structlog

from ichnaea.conf import settings
from ichnaea.exceptions import BaseClientError
from ichnaea.util import version_info


METRICS = markus.get_metrics()


def configure_logging(local_dev_env=None, logging_level=None):
    """Configure Python logging.

    :param local_dev_env: If True, format logs for humans. If False,
        use MozLog format for machines. The default is to read the
        value from settings.
    :param logging_level: The logging level, such as DEBUG or INFO.
        The default is to read the value from settings.
    """
    if local_dev_env is None:
        local_dev_env = settings("local_dev_env")
    if logging_level is None:
        logging_level = settings("logging_level")

    if local_dev_env:
        handlers = ["dev"]
        # Prepare structlog logs for local dev ProcessorFormatter
        structlog_fmt_prep = structlog.stdlib.ProcessorFormatter.wrap_for_formatter
        structlog_dev_processors = [
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
        ]
    else:
        handlers = ["mozlog"]
        # Prepare structlog logs for JsonLogFormatter
        structlog_fmt_prep = structlog.stdlib.render_to_log_kwargs
        structlog_dev_processors = []

    # Processors used for logs generated by structlog and stdlib's logging
    logging_config = {
        "version": 1,
        "disable_existing_loggers": True,
        "formatters": {
            "structlog_dev_console": {
                "()": structlog.stdlib.ProcessorFormatter,
                "processor": structlog.dev.ConsoleRenderer(colors=True),
                "foreign_pre_chain": structlog_dev_processors,
            },
            "mozlog_json": {
                "()": "dockerflow.logging.JsonLogFormatter",
                "logger_name": "ichnaea",
            },
        },
        "handlers": {
            "dev": {
                "class": "logging.StreamHandler",
                "formatter": "structlog_dev_console",
                "level": "DEBUG",
            },
            "mozlog": {
                "class": "logging.StreamHandler",
                "formatter": "mozlog_json",
                "level": "DEBUG",
            },
        },
        "loggers": {
            "alembic": {
                "propagate": False,
                "handlers": handlers,
                "level": logging_level,
            },
            "celery": {
                "propagate": False,
                "handlers": handlers,
                "level": logging_level,
            },
            "ichnaea": {
                "propagate": False,
                "handlers": handlers,
                "level": logging_level,
            },
            "markus": {
                "propagate": False,
                "handlers": handlers,
                "level": logging_level,
            },
            # https://stripe.com/blog/canonical-log-lines
            "canonical-log-line": {
                "propagate": False,
                "handlers": handlers,
                "level": logging_level,
            },
        },
        "root": {"handlers": handlers, "level": "WARNING"},
    }

    logging.config.dictConfig(logging_config)

    structlog_processors = (
        [structlog.contextvars.merge_contextvars, structlog.stdlib.filter_by_level]
        + structlog_dev_processors
        + [
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.UnicodeDecoder(),
            structlog_fmt_prep,
        ]
    )
    structlog.configure(
        processors=structlog_processors,
        logger_factory=structlog.stdlib.LoggerFactory(
            ignore_frame_names=["venusian", "pyramid.config"]
        ),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )


RAVEN_TRANSPORTS = {
    # Used in the webapp
    "gevent": GeventedHTTPTransport,
    # Used in the tests
    "sync": HTTPTransport,
    # Used in celery
    "threaded": ThreadedHTTPTransport,
}


def configure_raven(transport=None, tags=None, _client=None):
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
    environment = settings("sentry_environment")
    klass = DebugRavenClient if not dsn else RavenClient
    info = version_info()
    release = info.get("version") or info.get("commit") or "unknown"
    client = klass(
        dsn=dsn,
        transport=transport,
        release=release,
        environment=environment or None,
        tags=tags or {},
    )
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
    """A logging tween, handling collection of stats, exceptions, and a request log."""

    local_dev_env = settings("local_dev_env")

    def log_tween(request):
        """Time a request, emit metrics and log results, with exception handling."""
        start = time.time()
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(
            http_method=request.method, http_path=request.path
        )
        # Skip detailed logging and capturing for static assets, either in
        # /static or paths like /robots.txt
        is_static_content = (
            request.path in registry.skip_logging or request.path.startswith("/static")
        )

        def record_response(status_code):
            """Time request, (maybe) emit metrics, and (maybe) log this request.

            For static assets, metrics are skipped, and logs are skipped unless
            we're in the development environment.
            """
            duration = time.time() - start

            if not is_static_content:
                # Emit a request.timing and a request metric
                duration_ms = round(duration * 1000)
                # Convert a URI to to a statsd acceptable metric
                stats_path = (
                    request.path.replace("/", ".").lstrip(".").replace("@", "-")
                )
                # Use generate_tag to lowercase, truncate to 200 characters
                statsd_tags = [
                    # Homepage is ".homepage", would otherwise be empty string / True
                    generate_tag("path", stats_path or ".homepage"),
                    generate_tag("method", request.method),  # GET -> get, POST -> post
                ]
                METRICS.timing("request.timing", duration_ms, tags=statsd_tags)
                METRICS.incr(
                    "request",
                    tags=statsd_tags + [generate_tag("status", str(status_code))],
                )

            if local_dev_env or not is_static_content:
                # Emit a canonical-log-line
                duration_s = round(duration, 3)
                logger = structlog.get_logger("canonical-log-line")
                logger.info(
                    f"{request.method} {request.path} - {status_code}",
                    http_status=status_code,
                    duration_s=duration_s,
                )

        try:
            response = handler(request)
            record_response(response.status_code)
            return response
        except (BaseClientError, HTTPRedirection) as exc:
            # BaseClientError: 4xx error raise by Ichnaea API, other Ichnaea code
            # HTTPRedirection: 3xx redirect from Pyramid
            # Log, but do not send these exceptions to Sentry
            record_response(exc.status_code)
            raise
        except HTTPClientError:
            # HTTPClientError: 4xx error from Pyramid
            # Do not log or send to Sentry
            raise
        except HTTPException as exc:
            # HTTPException: Remaining 5xx (or maybe 2xx) errors from Pyramid
            # Log and send to Sentry
            record_response(exc.status_code)
            registry.raven_client.captureException()
            raise
        except Exception:
            # Any other exception, treat as 500 Internal Server Error
            # Treat as 500 Internal Server Error, log and send to Sentry
            record_response(500)
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
