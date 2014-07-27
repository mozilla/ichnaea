from ichnaea.app import main
from ichnaea.config import read_config

__all__ = ('application', 'main', )
_APP = None


def application(environ, start_response):  # pragma: no cover
    global _APP

    if _APP is None:
        conf = read_config()
        # Signal this call was made as part of app initialization
        _APP = main({}, heka_config=conf.filename, init=True,
                    **conf.get_map('ichnaea'))
        if environ is None and start_response is None:
            # Called as part of gunicorn's post_worker_init
            return _APP

    return _APP(environ, start_response)


# nosetests package level fixture setup/teardown

def setup_package(module):
    from ichnaea.tests.base import setup_package
    return setup_package(module)


def teardown_package(module):
    from ichnaea.tests.base import teardown_package
    return teardown_package(module)
