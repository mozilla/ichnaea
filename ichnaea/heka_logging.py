from StringIO import StringIO

from heka.config import client_from_text_config
from heka.holder import get_client

from ichnaea import config
from ichnaea.exceptions import BaseJSONError

RAVEN_ERROR = 'Unhandled error occured'


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

    client = get_client('ichnaea')
    client = client_from_text_config(merged_stream.read(), 'heka', client)

    return client


def heka_tween_factory(handler, registry):

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
        registry.heka_client.incr('http.request',
                                  fields={'status': str(response.status_code),
                                          'url_path': request.path})
        return response

    return heka_tween
