import os

from configparser import ConfigParser
from pyramid.config import Configurator
from pyramid.events import NewRequest
import statsd

from ichnaea.db import CellDB, MeasureDB
from ichnaea.renderer import DecimalJSON


def attach_dbs(event):
    request = event.request
    event.request.celldb = request.registry.celldb
    event.request.measuredb = request.registry.measuredb
    if hasattr(request.registry, 'queue'):
        event.request.queue = request.registry.queue


def main(global_config, **settings):
    config = Configurator(settings=settings)
    config.include("cornice")
    config.scan("ichnaea.views")
    settings = config.registry.settings

    # private config overrides
    private_config = settings.get('private')
    if private_config and os.path.isfile(private_config):
        parser = ConfigParser({'here': os.path.dirname(private_config)})
        parser.read([private_config])
        if parser.has_section('app:main'):
            main_section = parser['app:main']
            for name in ('celldb', 'measuredb'):
                value = main_section.get(name)
                if value:
                    settings[name] = value

    # retools queue
    if settings.get('async'):
        host = settings.get('redis.host', '127.0.0.0.1')
        port = int(settings.get('redis.port', '6379'))

        from redis import Redis
        _redis = Redis(host=host, port=port)

        from retools.queue import QueueManager
        config.registry.queue = QueueManager(_redis)

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
