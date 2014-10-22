from pyramid.config import Configurator
from pyramid.tweens import EXCVIEW
from redis.exceptions import ConnectionError
from sqlalchemy.exc import OperationalError
from sqlalchemy.sql import func, select

from ichnaea import customjson
from ichnaea.cache import redis_client
from ichnaea.db import (
    Database,
    db_master_session,
    db_slave_session,
    db_worker_session,
)
from ichnaea.geoip import configure_geoip


def main(global_config, heka_config=None, init=False,
         _db_master=None, _db_slave=None, _heka_client=None, _redis=None,
         _stats_client=None, **settings):
    config = Configurator(settings=settings)

    # add support for pt templates
    config.include('pyramid_chameleon')

    settings = config.registry.settings

    from ichnaea.content.views import configure_content
    from ichnaea.logging import configure_heka
    from ichnaea.logging import configure_stats
    from ichnaea.service import configure_service

    configure_content(config)
    configure_service(config)

    # configure databases incl. test override hooks
    if _db_master is None:
        config.registry.db_master = Database(settings['db_master'])
    else:
        config.registry.db_master = _db_master
    if _db_slave is None:
        config.registry.db_slave = Database(settings['db_slave'])
    else:
        config.registry.db_slave = _db_slave

    if _redis is None:
        config.registry.redis_client = None
        if 'redis_url' in settings:
            config.registry.redis_client = redis_client(settings['redis_url'])
    else:
        config.registry.redis_client = _redis

    if _heka_client is None:  # pragma: no cover
        config.registry.heka_client = heka_client = configure_heka(heka_config)
    else:
        config.registry.heka_client = heka_client = _heka_client

    config.registry.stats_client = configure_stats(
        settings.get('statsd_host'), _client=_stats_client)

    config.registry.geoip_db = configure_geoip(
        config.registry.settings, heka_client=heka_client)

    config.add_tween('ichnaea.db.db_tween_factory', under=EXCVIEW)
    config.add_tween('ichnaea.logging.log_tween_factory', under=EXCVIEW)
    config.add_request_method(db_master_session, property=True)
    config.add_request_method(db_slave_session, property=True)

    # replace json renderer with custom json variant
    config.add_renderer('json', customjson.Renderer())

    # Should we try to initialize and establish the outbound connections?
    if init:  # pragma: no cover
        # Test the slave DB connection
        with db_worker_session(config.registry.db_slave) as session:
            try:
                session.execute(select([func.now()])).first()
            except OperationalError:
                # Let the instance start, so it can recover / reconnect
                # to the DB later, but provide degraded service in the
                # meantime.
                pass

        # Test the redis connection
        try:
            config.registry.redis_client.ping()
        except ConnectionError:
            # Same as for the DB, continue with degraded service.
            pass

    return config.make_wsgi_app()
