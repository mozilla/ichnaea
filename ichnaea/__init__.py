

# nosetests package level fixture setup/teardown

def setup_package(module):
    # We do this here as early as possible in tests.
    # We only do it in tests, as the real celery processes should
    # run without the monkey patches applied. The gunicorn arbiter
    # patches its worker processes itself.
    from gevent import monkey
    monkey.patch_all()

    from ichnaea.tests.base import setup_package
    return setup_package(module)


def teardown_package(module):
    from ichnaea.tests.base import teardown_package
    return teardown_package(module)
