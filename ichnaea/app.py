from pyramid.config import Configurator
from pyramid.tweens import EXCVIEW

from ichnaea import customjson
from ichnaea.cache import redis_client
from ichnaea.content.views import configure_content
from ichnaea.db import (
    Database,
    db_rw_session,
    db_ro_session,
)
from ichnaea.geoip import configure_geoip
from ichnaea.logging import configure_raven
from ichnaea.logging import configure_stats
from ichnaea.service import configure_service


def main(global_config, app_config=None, init=False,
         _db_rw=None, _db_ro=None, _geoip_db=None,
         _raven_client=None, _redis=None, _stats_client=None):

    if app_config is not None:
        app_settings = app_config.get_map('ichnaea')
    else:
        app_settings = {}
    config = Configurator(settings=app_settings)

    # add support for pt templates
    config.include('pyramid_chameleon')

    settings = config.registry.settings

    configure_content(config)
    configure_service(config)

    # configure databases incl. test override hooks
    if _db_rw is None:
        config.registry.db_rw = Database(settings['db_master'])
    else:
        config.registry.db_rw = _db_rw
    if _db_ro is None:
        config.registry.db_ro = Database(settings['db_slave'])
    else:
        config.registry.db_ro = _db_ro

    if _redis is None:
        config.registry.redis_client = None
        if 'redis_url' in settings:
            config.registry.redis_client = redis_client(settings['redis_url'])
    else:
        config.registry.redis_client = _redis

    config.registry.raven_client = raven_client = configure_raven(
        settings.get('sentry_dsn'), _client=_raven_client)

    config.registry.stats_client = configure_stats(
        settings.get('statsd_host'), _client=_stats_client)

    config.registry.geoip_db = configure_geoip(
        settings.get('geoip_db_path'), raven_client=raven_client,
        _client=_geoip_db)

    config.add_tween('ichnaea.db.db_tween_factory', under=EXCVIEW)
    config.add_tween('ichnaea.logging.log_tween_factory', under=EXCVIEW)
    config.add_request_method(db_rw_session, property=True)
    config.add_request_method(db_ro_session, property=True)

    # replace json renderer with custom json variant
    config.add_renderer('json', customjson.Renderer())

    # Should we try to initialize and establish the outbound connections?
    if init:  # pragma: no cover
        registry = config.registry
        registry.db_ro.ping()
        registry.redis_client.ping()
        registry.stats_client.ping()

    return config.make_wsgi_app()
