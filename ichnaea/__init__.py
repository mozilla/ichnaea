from ichnaea.app import main
from ichnaea.config import read_config

__all__ = ('application', 'main', )
_APP = None


def application(environ, start_response):  # pragma: no cover
    global _APP

    if _APP is None:
        conf = read_config()
        _APP = main({}, heka_config=conf.filename, **conf.get_map('ichnaea'))

    return _APP(environ, start_response)


# nosetests package level fixture setup/teardown

def setup_package(module):
    from ichnaea.tests.base import setup_package
    return setup_package(module)


def teardown_package(module):
    from ichnaea.tests.base import teardown_package
    return teardown_package(module)
