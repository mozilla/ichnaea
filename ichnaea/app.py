import logging

from pyramid.config import Configurator
from pyramid.events import NewRequest
import statsd

from ichnaea.db import CellDB, MeasureDB
from ichnaea import decimaljson

logger = logging.getLogger('ichnaea')


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

    # logging
    global logger
    logger.setLevel(logging.DEBUG)
    sh = logging.StreamHandler()
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    sh.setFormatter(formatter)
    logger.addHandler(sh)

    config.registry.celldb = CellDB(settings['celldb'])
    config.registry.measuredb = MeasureDB(settings['measuredb'])
    config.add_subscriber(attach_dbs, NewRequest)

    # replace json renderer with decimal json variant
    config.add_renderer('json', decimaljson.Renderer())
    return config.make_wsgi_app()
