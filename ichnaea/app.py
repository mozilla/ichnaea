from pyramid.config import Configurator
from pyramid.tweens import EXCVIEW

from ichnaea import decimaljson
from ichnaea.db import Database, _Model
from ichnaea.db import archival_db_session
from ichnaea.db import volatile_db_session
from ichnaea.geoip import configure_geoip


def main(global_config, _archival_db=None, _volatile_db=None, **settings):
    config = Configurator(settings=settings)

    # add support for pt templates
    config.include('pyramid_chameleon')

    settings = config.registry.settings

    from ichnaea.content.views import configure_content
    from ichnaea.service import configure_service
    from ichnaea.heka_logging import configure_heka

    configure_content(config)
    configure_service(config)

    # configure databases incl. test override hooks
    if _archival_db is None:
        config.registry.archival_db = Database(
            settings['archival_db_url'],
            socket=settings.get('archival_db_socket'),
            model_class=_Model,
        )
    else:
        config.registry.archival_db = _archival_db
    if _volatile_db is None:
        config.registry.volatile_db = Database(
            settings['volatile_db_url'],
            socket=settings.get('volatile_db_socket'),
            model_class=_Model,
            create=False,
        )
    else:
        config.registry.volatile_db = _volatile_db

    config.registry.geoip_db = configure_geoip(config.registry.settings)

    config.registry.heka_client = configure_heka(config.registry.settings)

    config.add_tween('ichnaea.db.db_tween_factory', under=EXCVIEW)
    config.add_tween('ichnaea.heka_logging.heka_tween_factory', under=EXCVIEW)
    config.add_request_method(archival_db_session, property=True)
    config.add_request_method(volatile_db_session, property=True)

    # replace json renderer with decimal json variant
    config.add_renderer('json', decimaljson.Renderer())
    return config.make_wsgi_app()
