"""
Contains web app specific one time configuration code.
"""

from pyramid.config import Configurator
from pyramid.tweens import EXCVIEW

from ichnaea.api.config import configure_api
from ichnaea import floatjson
from ichnaea.cache import configure_redis
from ichnaea.content.views import configure_content
from ichnaea.db import (
    configure_db,
    db_rw_session,
    db_ro_session,
)
from ichnaea.geoip import configure_geoip
from ichnaea.log import (
    configure_logging,
    configure_raven,
    configure_stats,
)
from ichnaea.monitor import configure_monitor


def main(app_config, ping_connections=False,
         _db_rw=None, _db_ro=None, _geoip_db=None,
         _raven_client=None, _redis_client=None, _stats_client=None):
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

    configure_api(config)
    configure_content(config)
    configure_monitor(config)

    # configure outside connections
    registry = config.registry

    registry.db_rw = configure_db(
        app_config.get('ichnaea', 'db_master'), _db=_db_rw)
    registry.db_ro = configure_db(
        app_config.get('ichnaea', 'db_slave'), _db=_db_ro)

    registry.raven_client = raven_client = configure_raven(
        app_config.get('ichnaea', 'sentry_dsn'),
        transport='gevent', _client=_raven_client)

    registry.redis_client = configure_redis(
        app_config.get('ichnaea', 'redis_url'), _client=_redis_client)

    registry.stats_client = configure_stats(
        app_config.get('ichnaea', 'statsd_host'), _client=_stats_client)

    registry.geoip_db = configure_geoip(
        app_config.get('ichnaea', 'geoip_db_path'), raven_client=raven_client,
        _client=_geoip_db)

    config.add_tween('ichnaea.db.db_tween_factory', under=EXCVIEW)
    config.add_tween('ichnaea.log.log_tween_factory', under=EXCVIEW)
    config.add_request_method(db_rw_session, property=True)
    config.add_request_method(db_ro_session, property=True)

    # Add special JSON renderer with nicer float representation
    config.add_renderer('floatjson', floatjson.FloatJSONRenderer())

    # Should we try to initialize and establish the outbound connections?
    if ping_connections:  # pragma: no cover
        registry.db_ro.ping()
        registry.redis_client.ping()
        registry.stats_client.ping()

    return config.make_wsgi_app()
