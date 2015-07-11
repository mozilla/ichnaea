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

RAVEN_CLIENT = None
STATS_CLIENT = None

RAVEN_TRANSPORTS = {
    'gevent': GeventedHTTPTransport,
    'sync': HTTPTransport,
    'threaded': ThreadedHTTPTransport,
}


def get_raven_client():
    return RAVEN_CLIENT


def set_raven_client(client):
    global RAVEN_CLIENT
    RAVEN_CLIENT = client
    return RAVEN_CLIENT


def configure_raven(config, transport=None, _client=None):  # pragma: no cover
    if _client is not None:
        return set_raven_client(_client)

    transport = RAVEN_TRANSPORTS.get(transport)
    if not transport:
        raise ValueError('No valid raven transport was configured.')

    client = RavenClient(dsn=config, transport=transport)
    return set_raven_client(client)


def get_stats_client():
    return STATS_CLIENT


def set_stats_client(client):
    global STATS_CLIENT
    STATS_CLIENT = client
    return STATS_CLIENT


def configure_stats(config, _client=None):  # pragma: no cover
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
    return path.replace('/', '.').lstrip('.').replace('@', '-')


def configure_logging():
    logging.basicConfig()


def log_tween_factory(handler, registry):

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
        except Exception as exc:  # pragma: no cover
            timer_send()
            if isinstance(exc, HTTPException):
                status = exc.status_code
            else:
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

    def ping(self):
        stat = 'monitor.ping:1c'
        if self._prefix:  # pragma: no cover
            stat = '%s.%s' % (self._prefix, stat)
        try:
            self._sock.sendto(stat.encode('ascii'), self._addr)
        except socket.error:
            return False
        return True  # pragma: no cover


class DebugStatsClient(PingableStatsClient):

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
