import time

from heka.config import client_from_stream_config
from heka.holder import (
    CLIENT_HOLDER,
    get_client,
)
from pyramid.httpexceptions import (
    HTTPException,
    HTTPNotFound,
)

from ichnaea.exceptions import BaseJSONError


RAVEN_ERROR = 'Unhandled error occurred'


def get_heka_client():
    return get_client('ichnaea')


def set_heka_client(client):
    CLIENT_HOLDER.set_client('ichnaea', client)
    return get_heka_client()


def configure_heka(heka_config, _heka_client=None):
    if _heka_client is not None:
        return set_heka_client(_heka_client)

    client = get_heka_client()
    if heka_config:
        with open(heka_config, 'r') as fd:
            client = client_from_stream_config(fd, 'heka', client=client)
    return client


def quote_statsd_path(path):
    return path.replace('/', '.').lstrip('.').replace('@', '-')


def log_tween_factory(handler, registry):

    VALID_4xx_URLS = [
        '/v1/submit',
        '/v1/search',
        '/v1/geolocate',
        '/v1/geosubmit',
    ]

    def log_tween(request):
        heka_client = registry.heka_client
        stats_client = registry.stats_client
        start = time.time()

        def timer_send():
            duration = int(round((time.time() - start) * 1000))
            path = quote_statsd_path(request.path)
            stats_client.timing('request.' + path, duration)

        def counter_send(status_code):
            path = quote_statsd_path(request.path)
            stats_client.incr('request.%s.%s' % (path, status_code))

        try:
            response = handler(request)
        except HTTPNotFound:
            # ignore 404's raised as exceptions
            raise
        except BaseJSONError:
            # don't capture client JSON exceptions
            timer_send()
            counter_send(400)
            raise
        except Exception as exc:
            timer_send()
            if isinstance(exc, HTTPException):
                status = exc.status_code
            else:
                status = 500
            counter_send(status)
            heka_client.raven(RAVEN_ERROR)
            raise
        else:
            timer_send()

        # deal with non-exception 4xx responses
        resp_prefix = str(response.status_code)[0]
        if (resp_prefix == '4' and request.path in VALID_4xx_URLS) or \
           (resp_prefix != '4'):
            counter_send(response.status_code)

        return response

    return log_tween
