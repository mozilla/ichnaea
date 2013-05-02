import datetime

from pyramid.config import Configurator
from pyramid.events import NewRequest
import statsd

from ichnaea.db import CellDB, MeasureDB
from ichnaea import decimaljson


def attach_dbs(event):
    request = event.request
    event.request.celldb = request.registry.celldb
    event.request.measuredb = request.registry.measuredb
    if hasattr(request.registry, 'queue'):
        event.request.queue = request.registry.queue


def _is_true(value):
    if isinstance(value, str):
        value = value.lower() in ('true', '1')
    return value


def main(global_config, **settings):
    config = Configurator(settings=settings)
    config.include("cornice")
    config.scan("ichnaea.views")
    settings = config.registry.settings

    # retools queue
    if _is_true(settings.get('async')):
        host = settings.get('redis.host', '127.0.0.0.1')
        port = int(settings.get('redis.port', '6379'))

        from redis import Redis
        _redis = Redis(host=host, port=port)

        from retools.queue import QueueManager
        config.registry.queue = QueueManager(_redis)

    # batch settings
    batch_size = int(settings.get('batch_size', 100))
    settings['batch_size'] = batch_size
    batch_age = float(settings.get('batch_age', 600.0))
    settings['batch_age'] = datetime.timedelta(seconds=batch_age)

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
    config.add_renderer('json', decimaljson.Renderer())
    return config.make_wsgi_app()
