import logging
import os
from konfig import Config

from ichnaea.app import main  # NOQA

logger = logging.getLogger('ichnaea')

__all__ = ('logger', 'main')


_APP = None


def application(environ, start_response):  # pragma: no cover
    global _APP
    if _APP is None:
        config = os.environ.get('ICHNAEA_CFG', 'ichnaea.ini')
        config = Config(config)
        _APP = main({}, **config.get_map('ichnaea'))

    return _APP(environ, start_response)
