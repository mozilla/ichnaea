import time

from heka.config import client_from_stream_config
from heka.holder import get_client
from pyramid.httpexceptions import (
    HTTPException,
    HTTPNotFound,
)

from ichnaea.exceptions import BaseJSONError


RAVEN_ERROR = 'Unhandled error occurred'


def get_heka_client():
    return get_client('ichnaea')


def configure_heka(heka_config):
    client = get_heka_client()
    if heka_config:
        with open(heka_config, 'r') as fd:
            client = client_from_stream_config(fd, 'heka', client=client)
    return client


def heka_tween_factory(handler, registry):

    VALID_4xx_URLS = [
        '/v1/submit',
        '/v1/search',
        '/v1/geolocate',
        '/v1/geosubmit',
    ]

    def heka_tween(request):
        heka_client = registry.heka_client
        start = time.time()

        def timer_send():
            heka_client.timer_send(
                'http.request',
                time.time() - start, fields={'url_path': request.path})

        def counter_send(status_code):
            heka_client.incr(
                'http.request',
                fields={'status': str(status_code),
                        'url_path': request.path})

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

    return heka_tween
