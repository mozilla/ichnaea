"""Functionality related to statsd, sentry and freeform logging."""
from collections import deque
import logging
from logging.config import dictConfig
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

from ichnaea.config import RELEASE, TESTING
from ichnaea.exceptions import BaseClientError

LOGGER = logging.getLogger('ichnaea')

LOGGING_FORMAT = '%(asctime)s - %(levelname)-5.5s [%(name)s] %(message)s'
LOGGING_DATEFMT = '%Y-%m-%d %H:%M:%S'
LOGGING_CONFIG = dict(
    version=1,
    formatters={
        'generic': {
            'format': LOGGING_FORMAT,
            'datefmt': LOGGING_DATEFMT,
        },
    },
    handlers={
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'generic',
            'level': logging.DEBUG,
            'stream': 'ext://sys.stderr',
        },
    },
    root={
        'handlers': ['console'],
        'level': logging.WARN,
    },
    loggers=dict(
        alembic={
            'level': logging.INFO,
            'qualname': 'alembic',
        },
        ichnaea={
            'level': logging.INFO,
            'qualname': 'ichnaea',
        },
        sqlalchemny={
            'level': logging.WARN,
            'qualname': 'sqlalchemy.engine',
        },
    ),
)

RAVEN_CLIENT = None  #: The globally configured raven client.
STATS_CLIENT = None  #: The globally configured statsd client.

RAVEN_TRANSPORTS = {
    'gevent': GeventedHTTPTransport,
    'sync': HTTPTransport,
    'threaded': ThreadedHTTPTransport,
}  #: Mapping of raven transport names to classes.


def configure_logging():
    """Configure basic Python logging."""
    if TESTING:
        logging.basicConfig(
            format=LOGGING_FORMAT,
            datefmt=LOGGING_DATEFMT,
        )
    else:  # pragma: no cover
        dictConfig(LOGGING_CONFIG)


def configure_raven(app_config, transport=None,
                    _client=None):  # pragma: no cover
    """
    Configure, globally set and return a :class:`raven.Client` instance.

    :param transport: The transport to use, one of the
                      :data:`RAVEN_TRANSPORTS` keys.
    :param _client: Test-only hook to provide a pre-configured client.
    """
    global RAVEN_CLIENT
    if _client is not None:
        RAVEN_CLIENT = _client
        return _client

    transport = RAVEN_TRANSPORTS.get(transport)
    if not transport:
        raise ValueError('No valid raven transport was configured.')

    dsn = None
    if app_config and 'sentry' in app_config:
        section = app_config.get_map('sentry', {})
        dsn = section.get('dsn', None)

    klass = RavenClient if dsn is not None else DebugRavenClient
    client = klass(dsn=dsn, transport=transport, release=RELEASE)
    RAVEN_CLIENT = client
    return client


def configure_stats(app_config, _client=None):  # pragma: no cover
    """
    Configure, globally set and return a
    :class:`~ichnaea.log.StatsClient` instance.

    :param _client: Test-only hook to provide a pre-configured client.
    """
    global STATS_CLIENT
    if _client is not None:
        STATS_CLIENT = _client
        return _client

    klass = DebugStatsClient
    host = 'localhost'
    port = 9
    namespace = 'location'
    tag_support = True

    if app_config and 'statsd' in app_config:
        section = app_config.get_map('statsd', {})
        host = section.get('host', None)
        port = section.get('port', None)
        if host is not None and port is not None:
            klass = StatsClient
        if host is not None:
            host = host.strip()
        else:
            host = 'localhost'
        if port is not None:
            port = int(port)
        else:
            port = 9
        namespace = section.get('metric_prefix', 'location').strip()
        tag_support = asbool(section.get('tag_support', 'false').strip())

    client = klass(
        host=host, port=port, namespace=namespace,
        tag_support=tag_support)
    STATS_CLIENT = client
    return client


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
        self.msgs = deque(maxlen=10)

    def _clear(self):
        self.msgs.clear()
        self.context.clear()

    def is_enabled(self):
        return True

    def send(self, auth_header=None, **data):
        self.msgs.append(data)
        self.state.set_success()

    def check(self, expected=()):
        """
        Checks the raven message stream looking for the expected messages.

        The expected argument should be a list of either names or tuples.

        If it is a tuple, it should be a tuple of name and an expected count.

        The names are matched via startswith against the captured exception
        messages.
        """
        messages = [msg['message'] for msg in self.msgs]
        matched_msgs = []
        for exp in expected:
            count = 1
            name = exp
            if isinstance(exp, tuple):
                name, count = exp
            matches = [msg for msg in self.msgs
                       if msg['message'].startswith(name)]
            matched_msgs.extend(matches)
            assert len(matches) == count, messages

        for msg in matched_msgs:
            self.msgs.remove(msg)


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

    def close(self):
        if self.socket:  # pragma: no cover
            self.socket.close()
            self.socket = None

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

    def _find_messages(self, msg_type, msg_name, msg_value=None, msg_tags=()):
        data = {
            'counter': [],
            'timer': [],
            'gauge': [],
            'histogram': [],
            'meter': [],
            'set': [],
        }
        for msg in self.msgs:
            tags = ()
            if '|#' in msg:
                parts = msg.split('|#')
                tags = parts[-1].split(',')
                msg = parts[0]
            suffix = msg.split('|')[-1]
            name, value = msg.split('|')[0].split(':')
            value = int(value)
            if suffix == 'g':
                data['gauge'].append((name, value, tags))
            elif suffix == 'ms':
                data['timer'].append((name, value, tags))
            elif suffix.startswith('c'):
                data['counter'].append((name, value, tags))
            elif suffix == 'h':
                data['histogram'].append((name, value, tags))
            elif suffix == 'm':  # pragma: no cover
                data['meter'].append((name, value, tags))
            elif suffix == 's':
                data['set'].append((name, value, tags))

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
                    else:  # pragma: no cover
                        raise TypeError('wanted 2, 3 or 4 tuple, got %s'
                                        % type(pred))
                else:  # pragma: no cover
                    raise TypeError('wanted str or tuple, got %s'
                                    % type(pred))
                msgs = self._find_messages(msg_type, name, value, tags)
                if isinstance(match, int):
                    assert match == len(msgs)
