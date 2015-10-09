# Disable deprecation warnings in production mode
import os.path
import sys
import warnings

from pymysql import err

warnings.simplefilter('ignore', DeprecationWarning)
warnings.simplefilter('ignore', PendingDeprecationWarning)
warnings.simplefilter('ignore', err.Warning)

# Enable pyopenssl based SSL stack
if sys.version_info < (3, 0):  # pragma: no cover
    from requests.packages.urllib3.contrib import pyopenssl
    pyopenssl.inject_into_urllib3()
    del pyopenssl

ROOT = os.path.abspath(os.path.dirname(__file__))


def setup_package(module):
    # nosetests package level fixture setup

    # We do this here as early as possible in tests.
    # We only do it in tests, as the real celery processes should
    # run without the monkey patches applied. The gunicorn arbiter
    # patches its worker processes itself.
    from gevent import monkey
    monkey.patch_all()

    # enable all warnings in test mode
    warnings.resetwarnings()
    warnings.simplefilter('default')
    warnings.simplefilter('ignore', err.Warning)

    from ichnaea.tests.base import setup_package
    return setup_package(module)


def teardown_package(module):
    # nosetests package level fixture setup

    from ichnaea.tests.base import teardown_package
    return teardown_package(module)


__all__ = ('setup_package', 'teardown_package')
