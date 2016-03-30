"""
Contains web app specific one time configuration code.
"""

from pyramid.config import Configurator
from pyramid.tweens import EXCVIEW

from ichnaea.api.config import configure_api
from ichnaea.api.locate.searcher import (
    configure_position_searcher,
    configure_region_searcher,
)
from ichnaea.cache import configure_redis
from ichnaea.content.views import configure_content
from ichnaea.db import (
    configure_db,
    db_ro_session,
)
from ichnaea import floatjson
from ichnaea.geoip import configure_geoip
from ichnaea.http import configure_http_session
from ichnaea.log import (
    configure_logging,
    configure_raven,
    configure_stats,
)
from ichnaea.queue import DataQueue
from ichnaea.webapp.monitor import configure_monitor


def main(app_config, ping_connections=False,
         _db_rw=None, _db_ro=None, _geoip_db=None, _http_session=None,
         _raven_client=None, _redis_client=None, _stats_client=None,
         _position_searcher=None, _region_searcher=None):
    """
    Configure the web app stored in :data:`ichnaea.webapp.app._APP`.

    Does connection, logging and view config setup. Attaches some
    additional functionality to the :class:`pyramid.registry.Registry`
    instance.

    At startup ping all outbound connections like the database
    once, to ensure they are actually up and responding.

    The parameters starting with an underscore are test-only hooks
    to provide pre-configured connection objects.

    :param app_config: The parsed application ini.
    :type app_config: :class:`ichnaea.config.Config`

    :param ping_connections: If True, ping and test outside connections.
    :type ping_connections: bool

    :returns: A configured WSGI app, the result of calling
              :meth:`pyramid.config.Configurator.make_wsgi_app`.
    """

    configure_logging()

    # make config file settings available
    config = Configurator(settings=app_config.asdict())

    # add support for pt templates
    config.include('pyramid_chameleon')

    # add a config setting to skip logging for some views
    config.registry.skip_logging = set()

    configure_api(config)
    configure_content(config)
    configure_monitor(config)

    # configure outside connections
    registry = config.registry

    registry.db_rw = configure_db(
        app_config.get('database', 'rw_url'), _db=_db_rw)
    registry.db_ro = configure_db(
        app_config.get('database', 'ro_url'), _db=_db_ro)

    registry.raven_client = raven_client = configure_raven(
        app_config.get('sentry', 'dsn'),
        transport='gevent', _client=_raven_client)

    registry.redis_client = redis_client = configure_redis(
        app_config.get('cache', 'cache_url'), _client=_redis_client)

    registry.stats_client = stats_client = configure_stats(
        app_config, _client=_stats_client)

    registry.http_session = configure_http_session(_session=_http_session)

    registry.geoip_db = geoip_db = configure_geoip(
        app_config.get('geoip', 'db_path'), raven_client=raven_client,
        _client=_geoip_db)

    for name, func, default in (('position_searcher',
                                 configure_position_searcher,
                                 _position_searcher),
                                ('region_searcher',
                                 configure_region_searcher,
                                 _region_searcher)):
        searcher = func(geoip_db=geoip_db, raven_client=raven_client,
                        redis_client=redis_client, stats_client=stats_client,
                        _searcher=default)
        setattr(registry, name, searcher)

    # needs to be the exact same as async.config
    registry.data_queues = {
        'update_incoming': DataQueue('update_incoming', redis_client,
                                     batch=100, compress=True),
    }

    config.add_tween('ichnaea.db.db_tween_factory', under=EXCVIEW)
    config.add_tween('ichnaea.log.log_tween_factory', under=EXCVIEW)
    config.add_request_method(db_ro_session, property=True)

    # Add special JSON renderer with nicer float representation
    config.add_renderer('floatjson', floatjson.FloatJSONRenderer())

    # freeze skip logging set
    config.registry.skip_logging = frozenset(config.registry.skip_logging)

    # Should we try to initialize and establish the outbound connections?
    if ping_connections:  # pragma: no cover
        registry.db_ro.ping()
        registry.redis_client.ping()

    return config.make_wsgi_app()
