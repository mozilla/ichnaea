import logging
import os
import StringIO
from konfig import Config

from ichnaea.app import main  # NOQA

logger = logging.getLogger('ichnaea')

__all__ = ('logger', 'main')


_APP = None


def application(environ, start_response):
    global _APP
    if _APP is None:
        config = os.environ.get('ICHNAEA_CFG', 'ichnaea.ini')

        with open(config) as f:
            cfg = f.read()
            # backward compat with Paste
            cfg = cfg.replace('%(here)s', os.path.dirname(__file__))

        config = Config(StringIO.StringIO(cfg))
        _APP = main({}, **config.get_map('app:main'))

    return _APP(environ, start_response)
