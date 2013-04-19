import logging

from pyramid.config import Configurator
from pyramid.events import NewRequest
import statsd

from ichnaea.db import Database
from ichnaea.renderer import DecimalJSON

logger = logging.getLogger('ichnaea')


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

    config.registry.db = Database(settings['database'])
    config.add_subscriber(attach_db_session, NewRequest)

    # replace json renderer with decimal json variant
    config.add_renderer('json', DecimalJSON())
    return config.make_wsgi_app()
