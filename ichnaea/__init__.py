import os
from konfig import Config

from ichnaea.app import main  # NOQA

__all__ = ('application', 'config', 'main', )
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


# nosetests package level fixture setup/teardown

def setup_package(module):
    from ichnaea.tests.base import setup_package
    return setup_package(module)


def teardown_package(module):
    from ichnaea.tests.base import teardown_package
    return teardown_package(module)
