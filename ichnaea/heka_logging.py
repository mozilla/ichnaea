
def configure_heka(registry_settings={}):
    # If a test client is defined just use that instead of whatever is
    # defined in the configuration
    if '_heka_client' in registry_settings:
        return registry_settings['_heka_client']

    from ichnaea import config
    import os
    from heka.config import client_from_text_config
    from heka.holder import get_client

    ichnaea_ini = os.path.abspath(config().filename)
    client = get_client('ichnaea')
    client = client_from_text_config(open(ichnaea_ini).read(), 'heka', client)

    return client


def heka_tween_factory(handler, registry):

    def heka_tween(request):

        with registry.heka_client.timer('http.request',
                                        fields={'url_path': request.path}):
            response = handler(request)
        registry.heka_client.incr('http.request',
                                  fields={'status': str(response.status_code),
                                          'url_path': request.path})
        return response

    return heka_tween
