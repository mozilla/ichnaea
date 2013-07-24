import logging

from pyramid.config import Configurator
from pyramid.events import NewRequest

from ichnaea import decimaljson
from ichnaea.db import Database
from ichnaea.views import robotstxt_view

logger = logging.getLogger('ichnaea')


def attach_database(event):
    request = event.request
    event.request.database = request.registry.database


def main(global_config, **settings):
    config = Configurator(settings=settings)
    config.include("cornice")
    config.scan("ichnaea.views")
    settings = config.registry.settings

    # logging
    global logger
    logger.setLevel(logging.DEBUG)
    sh = logging.StreamHandler()
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    sh.setFormatter(formatter)
    logger.addHandler(sh)
    waitress_log = logging.getLogger('waitress')
    waitress_log.addHandler(sh)

    config.add_static_view(
        name='static', path='ichnaea:static', cache_max_age=3600)
    config.add_route('robots', '/robots.txt')
    config.add_view(robotstxt_view, route_name='robots', http_cache=86400)

    config.registry.database = Database(settings['database'])
    config.add_subscriber(attach_database, NewRequest)

    # replace json renderer with decimal json variant
    config.add_renderer('json', decimaljson.Renderer())
    return config.make_wsgi_app()
