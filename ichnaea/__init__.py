# Disable deprecation warnings in production mode
import warnings
warnings.simplefilter('ignore', DeprecationWarning)

# Enable pyopenssl based SSL stack
from requests.packages.urllib3.contrib import pyopenssl  # NOQA
pyopenssl.inject_into_urllib3()
del pyopenssl


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

    from ichnaea.tests.base import setup_package
    return setup_package(module)
