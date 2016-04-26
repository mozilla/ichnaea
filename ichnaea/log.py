"""Functionality related to statsd, sentry and freeform logging."""
from collections import deque
import logging
from random import random
import time

from pyramid.httpexceptions import (
    HTTPException,
    HTTPClientError,
    HTTPRedirection,
)
from pyramid.settings import asbool
from raven import Client as RavenClient
from raven.transport.gevent import GeventedHTTPTransport
from raven.transport.http import HTTPTransport
from raven.transport.threaded import ThreadedHTTPTransport
from datadog.dogstatsd.base import (
    DogStatsd,
    imap,
)

from ichnaea.config import RELEASE
from ichnaea.exceptions import BaseClientError

RAVEN_CLIENT = None  #: The globally configured raven client.
STATS_CLIENT = None  #: The globally configured statsd client.

RAVEN_TRANSPORTS = {
    'gevent': GeventedHTTPTransport,
    'sync': HTTPTransport,
    'threaded': ThreadedHTTPTransport,
}  #: Mapping of raven transport names to classes.


def get_raven_client():  # pragma: no cover
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

    client = RavenClient(dsn=config, transport=transport, release=RELEASE)
    return set_raven_client(client)


def get_stats_client():  # pragma: no cover
    """Return the globally configured statsd client."""
    return STATS_CLIENT


def set_stats_client(client):
    """Set the global statsd client."""
    global STATS_CLIENT
    STATS_CLIENT = client
    return STATS_CLIENT


def configure_stats(app_config, _client=None):  # pragma: no cover
    """
    Configure, globally set and return a
    :class:`~ichnaea.log.StatsClient` instance.

    :param _client: Test-only hook to provide a pre-configured client.
    """
    if _client is not None:
        return set_stats_client(_client)

    if not app_config:
        host = 'localhost'
        port = 8125
        namespace = 'location'
        tag_support = False
    else:
        section = app_config.get_map('statsd', {})
        host = section.get('host', 'localhost').strip()
        port = int(section.get('port', 8125))
        namespace = section.get('metric_prefix', 'location').strip()
        tag_support = asbool(section.get('tag_support', 'false').strip())

    client = StatsClient(
        host=host, port=port, namespace=namespace,
        tag_support=tag_support)

    return set_stats_client(client)


def configure_logging():
    """Configure basic Python logging."""
    logging.basicConfig(
        format='%(asctime)s - %(levelname)-5.5s [%(name)s] %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S',
    )


def log_tween_factory(handler, registry):
    """A logging tween, doing automatic statsd and raven collection."""

    def log_tween(request):
        if (request.path in registry.skip_logging or
                request.path.startswith('/static')):
            # shortcut handling for static assets
            try:
                return handler(request)
            except HTTPException:  # pragma: no cover
                # don't capture exceptions for normal responses
                raise
            except Exception:  # pragma: no cover
                registry.raven_client.captureException()
                raise

        stats_client = registry.stats_client
        start = time.time()
        statsd_tags = [
            # Convert a URI to a statsd acceptable metric name
            'path:%s' % request.path.replace(
                '/', '.').lstrip('.').replace('@', '-'),
            'method:%s' % request.method.lower(),
        ]

        def timer_send():
            duration = int(round((time.time() - start) * 1000))
            stats_client.timing('request', duration, tags=statsd_tags)

        def counter_send(status_code):
            stats_client.incr('request',
                              tags=statsd_tags + ['status:%s' % status_code])

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
            else:  # pragma: no cover
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
        self.state.set_success()


class StatsClient(DogStatsd):
    """A statsd client."""

    def __init__(self, host='localhost', port=8125, max_buffer_size=50,
                 namespace=None, constant_tags=None, use_ms=False,
                 tag_support=False):
        super(StatsClient, self).__init__(
            host=host, port=port,
            max_buffer_size=max_buffer_size,
            namespace=namespace,
            constant_tags=constant_tags,
            use_ms=True)  # always enable this to be standards compliant
        self.tag_support = tag_support

    def _report(self, metric, metric_type, value, tags, sample_rate):
        if value is None:  # pragma: no cover
            return

        if sample_rate != 1 and random() > sample_rate:  # pragma: no cover
            return

        payload = []

        # Resolve the full tag list
        if self.constant_tags:  # pragma: no cover
            if tags:
                tags = tags + self.constant_tags
            else:
                tags = self.constant_tags

        # Create/format the metric packet
        if self.namespace:
            payload.append(self.namespace + '.')

        if tags and not self.tag_support:
            # append tags to the metric name
            tags = '.'.join([tag.replace(':', '_') for tag in tags])
            if tags:
                metric += '.' + tags

        payload.extend([metric, ':', value, '|', metric_type])

        if sample_rate != 1:  # pragma: no cover
            payload.extend(['|@', sample_rate])

        if tags and self.tag_support:
            # normal tag support
            payload.extend(['|#', ','.join(tags)])

        encoded = ''.join(imap(str, payload))

        # Send it
        self._send(encoded)

    def incr(self, *args, **kw):
        return self.increment(*args, **kw)


class DebugStatsClient(StatsClient):
    """An in-memory statsd client with an inspectable message queue."""

    def __init__(self, host='localhost', port=8125, max_buffer_size=50,
                 namespace=None, constant_tags=None, use_ms=False,
                 tag_support=False):
        super(DebugStatsClient, self).__init__(
            host=host, port=port,
            max_buffer_size=max_buffer_size,
            namespace=namespace,
            constant_tags=constant_tags,
            use_ms=use_ms,
            tag_support=tag_support)
        self.msgs = deque(maxlen=100)

    def _clear(self):
        self.msgs.clear()

    def _send_to_server(self, packet):
        self.msgs.append(packet)
