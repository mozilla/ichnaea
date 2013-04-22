from pyramid.config import Configurator
from pyramid.events import NewRequest
import statsd

from ichnaea.db import CellDB, MeasureDB
from ichnaea.renderer import DecimalJSON


def attach_dbs(event):
    request = event.request
    event.request.celldb = request.registry.celldb
    event.request.measuredb = request.registry.measuredb


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

    config.registry.celldb = CellDB(settings['celldb'])
    config.registry.measuredb = MeasureDB(settings['measuredb'])
    config.add_subscriber(attach_dbs, NewRequest)

    # replace json renderer with decimal json variant
    config.add_renderer('json', DecimalJSON())
    return config.make_wsgi_app()
