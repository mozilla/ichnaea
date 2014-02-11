from pyramid.config import Configurator
from pyramid.tweens import EXCVIEW

from ichnaea import decimaljson
from ichnaea.db import Database
from ichnaea.db import db_master_session
from ichnaea.db import db_slave_session


def main(global_config, _db_master=None, _db_slave=None, **settings):
    config = Configurator(settings=settings)
    settings = config.registry.settings

    from ichnaea.content.views import configure_content
    from ichnaea.service import configure_service
    from ichnaea.heka_logging import configure_heka

    configure_content(config)
    configure_service(config)

    # configure databases incl. test override hooks
    if _db_master is None:
        config.registry.db_master = Database(
            settings['db_master'],
            socket=settings.get('db_master_socket'),
        )
    else:
        config.registry.db_master = _db_master
    if _db_slave is None:
        config.registry.db_slave = Database(
            settings['db_slave'],
            socket=settings.get('db_slave_socket'),
            create=False,
        )
    else:
        config.registry.db_slave = _db_slave

    config.registry.heka_client = configure_heka(config.registry.settings)

    config.add_tween('ichnaea.db.db_tween_factory', under=EXCVIEW)
    config.add_tween('ichnaea.heka_logging.heka_tween_factory', under=EXCVIEW)
    config.add_request_method(db_master_session, property=True)
    config.add_request_method(db_slave_session, property=True)

    # replace json renderer with decimal json variant
    config.add_renderer('json', decimaljson.Renderer())
    return config.make_wsgi_app()
