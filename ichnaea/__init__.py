import decimal
import logging

import simplejson as json
from pyramid.config import Configurator
from pyramid.events import NewRequest
import statsd

from ichnaea.db import Database

logger = logging.getLogger('ichnaea')


class DecimalJSON(object):
    def __init__(self, jsonp_param_name='callback'):
        self.jsonp_param_name = jsonp_param_name

    def __call__(self, info):
        def _render(value, system):
            with decimal.localcontext() as ctx:
                ctx.prec = 5
                ret = json.dumps(value, use_decimal=True)
            request = system.get('request')
            if request is not None:
                callback = request.params.get(self.jsonp_param_name)
                if callback is None:
                    request.response.content_type = 'application/json'
                else:
                    request.response.content_type = 'text/javascript'
                    ret = '%(callback)s(%(json)s);' % {
                        'callback': callback,
                        'json': ret
                    }
            return ret
        return _render


def attach_db_session(event):
    request = event.request
    event.request.db_session = request.registry.db.session()


def main(global_config, **settings):
    config = Configurator(settings=settings)
    config.include("cornice")
    config.scan("ichnaea.views")
    settings = config.registry.settings

    # statsd settings
    statsd_settings = {
        'STATSD_HOST': settings.get('statsd.host', 'localhost'),
        'STATSD_PORT': int(settings.get('statsd.port', 8125)),
        'STATSD_SAMPLE_RATE': float(settings.get('statsd.sample', 1.0)),
        'STATSD_BUCKET_PREFIX': settings.get('statsd.prefix', ''),
    }

    statsd.init_statsd(statsd_settings)

    cors_origins = settings.get('cors.origins', '*')
    cors_origins = cors_origins.split(',')

    config.registry.db = Database(settings['database'])
    config.add_subscriber(attach_db_session, NewRequest)

    # add decimal json renderer
    config.add_renderer('decimaljson', DecimalJSON())
    return config.make_wsgi_app()
