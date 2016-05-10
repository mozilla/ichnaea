import gc
import warnings

import pytest


@pytest.yield_fixture(scope='session', autouse=True)
def package():
    # We do this here as early as possible in tests.
    # We only do it in tests, as the real celery processes should
    # run without the monkey patches applied. The gunicorn arbiter
    # patches its worker processes itself.
    from gevent import monkey
    monkey.patch_all()

    # Enable all warnings in test mode.
    warnings.resetwarnings()
    warnings.simplefilter('default')

    # Look for memory leaks.
    gc.set_debug(gc.DEBUG_UNCOLLECTABLE)

    # Make sure all models are imported.
    from ichnaea import models  # NOQA

    # Setup clean database tables.
    from ichnaea.tests.base import DBTestCase
    DBTestCase.setup_database()

    yield None

    # Print memory leaks.
    if gc.garbage:  # pragma: no cover
        print('Uncollectable objects found:')
        for obj in gc.garbage:
            print(obj)
