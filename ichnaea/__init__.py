# Disable deprecation warnings in production mode
import warnings
warnings.simplefilter('ignore', DeprecationWarning)

# TODO: Disable SSL warnings for now
from requests.packages import urllib3  # NOQA
urllib3.disable_warnings()


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

    # ignore warning for ichnaea.db.on_duplicate hack
    from sqlalchemy.exc import SAWarning
    warnings.filterwarnings(
        'ignore', ".*SQLAlchemy dialect named 'on'$", SAWarning)

    from ichnaea.tests.base import setup_package
    return setup_package(module)
