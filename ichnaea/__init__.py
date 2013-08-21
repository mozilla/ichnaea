import logging
import os
from konfig import Config

from ichnaea.app import main  # NOQA

logger = logging.getLogger('ichnaea')

__all__ = ('logger', 'main')


_APP = None


def config():
    ini = os.environ.get('ICHNAEA_CFG', 'ichnaea.ini')
    return Config(ini)


def application(environ, start_response):  # pragma: no cover
    global _APP
    if _APP is None:
        conf = config()
        _APP = main({}, **conf.get_map('ichnaea'))

    return _APP(environ, start_response)
