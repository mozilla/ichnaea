import logging

from pyramid.config import Configurator

from ichnaea import decimaljson
from ichnaea.db import Database
from ichnaea.content.views import configure_content

logger = logging.getLogger('ichnaea')


def db_session(request):
    session = request.registry.database.session()

    def cleanup(request):
        session.close()
    request.add_finished_callback(cleanup)
    return session


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

    configure_content(config)

    config.registry.database = Database(
        settings['database'], settings.get('unix_socket'))
    config.add_request_method(db_session, reify=True)

    # replace json renderer with decimal json variant
    config.add_renderer('json', decimaljson.Renderer())
    return config.make_wsgi_app()
