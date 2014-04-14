from StringIO import StringIO

from heka.config import client_from_text_config
from heka.holder import get_client
from heka.client import HekaClient

from ichnaea import config
from ichnaea.exceptions import BaseJSONError

import random

RAVEN_ERROR = 'Unhandled error occured'


def get_heka_client():
    return get_client('ichnaea')


def configure_heka(registry_settings={}):
    # If a test client is defined just use that instead of whatever is
    # defined in the configuration
    if '_heka_client' in registry_settings:
        return registry_settings['_heka_client']

    # deal with konfig's include/extends syntax and construct a merged
    # file-like object from all the files
    merged_stream = StringIO()
    konfig = config()
    konfig.write(merged_stream)
    merged_stream.seek(0)

    client = get_heka_client()
    client = client_from_text_config(merged_stream.read(), 'heka', client)

    return client


def heka_tween_factory(handler, registry):

    VALID_4xx_URLS = ['/v1/submit', '/v1/search', '/v1/geolocate']

    def heka_tween(request):
        with registry.heka_client.timer('http.request',
                                        fields={'url_path': request.path}):
            try:
                response = handler(request)
            except BaseJSONError:
                # don't send client JSON errors via raven
                raise
            except Exception:
                registry.heka_client.raven(RAVEN_ERROR)
                raise

        resp_prefix = str(response.status_code)[0]
        if (resp_prefix == '4' and request.path in VALID_4xx_URLS) or \
           (resp_prefix != '4'):
            registry.heka_client.incr(
                'http.request',
                fields={'status': str(response.status_code),
                        'url_path': request.path})
        return response

    return heka_tween


# Temporarily monkey-patch heka.client.HekaClient until upstream releases
# an updated version. See https://github.com/mozilla-services/heka-py/pull/20

def gauge(self, name, value, logger=None, severity=None, fields=None,
          rate=1.0):
    """Sends an 'current gauge measurement' message.

    :param name: String label for the gauge.
    :param value: Number current absolute value of the gauge.
    :param logger: String token identifying the message generator.
    :param severity: Numerical code (0-7) for msg severity, per RFC
                     5424.
    :param fields: Arbitrary key/value pairs for add'l metadata.

    """
    if rate < 1 and random.random() >= rate:
        return
    payload = str(value)
    fields = fields if fields is not None else dict()
    fields['name'] = name
    fields['rate'] = rate
    self.heka('gauge', logger, severity, payload, fields)

if not hasattr(HekaClient, 'gauge'):
    HekaClient.gauge = gauge
