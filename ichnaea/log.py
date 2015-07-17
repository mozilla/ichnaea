"""Functionality related to statsd, sentry and freeform logging."""
from collections import deque
import logging
import socket
import time

from pyramid.httpexceptions import (
    HTTPException,
    HTTPClientError,
    HTTPRedirection,
)
from raven import Client as RavenClient
from raven.transport.gevent import GeventedHTTPTransport
from raven.transport.http import HTTPTransport
from raven.transport.threaded import ThreadedHTTPTransport
from statsd.client import StatsClient

from ichnaea.exceptions import BaseClientError

RAVEN_CLIENT = None  #: The globally configured raven client.
STATS_CLIENT = None  #: The globally configured statsd client.

RAVEN_TRANSPORTS = {
    'gevent': GeventedHTTPTransport,
    'sync': HTTPTransport,
    'threaded': ThreadedHTTPTransport,
}  #: Mapping of raven transport names to classes.


def get_raven_client():
    """Return the globally configured raven client."""
    return RAVEN_CLIENT


def set_raven_client(client):
    """Set the global raven client."""
    global RAVEN_CLIENT
    RAVEN_CLIENT = client
    return RAVEN_CLIENT


def configure_raven(config, transport=None, _client=None):  # pragma: no cover
    """
    Configure, globally set and return a :class:`raven.Client` instance.

    :param transport: The transport to use, one of the
                      :data:`RAVEN_TRANSPORTS` keys.
    :param _client: Test-only hook to provide a pre-configured client.
    """
    if _client is not None:
        return set_raven_client(_client)

    transport = RAVEN_TRANSPORTS.get(transport)
    if not transport:
        raise ValueError('No valid raven transport was configured.')

    client = RavenClient(dsn=config, transport=transport)
    return set_raven_client(client)


def get_stats_client():
    """Return the globally configured statsd client."""
    return STATS_CLIENT


def set_stats_client(client):
    """Set the global statsd client."""
    global STATS_CLIENT
    STATS_CLIENT = client
    return STATS_CLIENT


def configure_stats(config, _client=None):  # pragma: no cover
    """
    Configure, globally set and return a
    :class:`~ichnaea.log.PingableStatsClient` instance.

    :param _client: Test-only hook to provide a pre-configured client.
    """
    if _client is not None:
        return set_stats_client(_client)

    if not config:
        config = 'localhost:8125'
    parts = config.split(':')
    host = parts[0]
    port = 8125
    if len(parts) > 1:
        port = int(parts[1])

    client = PingableStatsClient(host=host, port=port, prefix='location')
    return set_stats_client(client)


def quote_statsd_path(path):
    """Convert a URI to a statsd acceptable metric name."""
    return path.replace('/', '.').lstrip('.').replace('@', '-')


def configure_logging():
    """Configure basic Python logging."""
    logging.basicConfig()


def log_tween_factory(handler, registry):
    """A logging tween, doing automatic statsd and raven collection."""

    def log_tween(request):
        raven_client = registry.raven_client
        stats_client = registry.stats_client
        start = time.time()
        statsd_path = quote_statsd_path(request.path)

        def timer_send():
            duration = int(round((time.time() - start) * 1000))
            stats_client.timing('request.' + statsd_path, duration)

        def counter_send(status_code):
            stats_client.incr('request.%s.%s' % (statsd_path, status_code))

        try:
            response = handler(request)
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
            else:  # pragma: no cover
                status = 500
            counter_send(status)
            raven_client.captureException()
            raise
        else:
            timer_send()
            counter_send(response.status_code)

        return response

    return log_tween


class DebugRavenClient(RavenClient):
    """An in-memory raven client with an inspectable message queue."""

    def __init__(self, *args, **kw):
        super(DebugRavenClient, self).__init__(*args, **kw)
        self.msgs = deque(maxlen=100)

    def _clear(self):
        self.msgs.clear()

    def is_enabled(self):
        return True

    def send(self, auth_header=None, **data):
        self.msgs.append(data)


class PingableStatsClient(StatsClient):
    """A pingable statsd client."""

    def ping(self):
        """
        Ping the Statsd server. On success return `True`, otherwise `False`.
        """
        stat = 'monitor.ping:1c'
        if self._prefix:  # pragma: no cover
            stat = '%s.%s' % (self._prefix, stat)
        try:
            self._sock.sendto(stat.encode('ascii'), self._addr)
        except socket.error:
            return False
        return True  # pragma: no cover


class DebugStatsClient(PingableStatsClient):
    """An in-memory statsd client with an inspectable message queue."""

    def __init__(self, host='localhost', port=8125, prefix=None,
                 maxudpsize=512):
        self._host = host
        self._port = port
        self._addr = None
        self._sock = None
        self._prefix = prefix
        self._maxudpsize = maxudpsize
        self.msgs = deque(maxlen=100)

    def _clear(self):
        self.msgs.clear()

    def _send(self, data):
        self.msgs.append(data)

    def ping(self):
        return True
