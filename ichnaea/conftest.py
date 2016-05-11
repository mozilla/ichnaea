import gc
import os
import warnings

from maxminddb.const import MODE_AUTO
import pytest
import webtest

from ichnaea.api.locate.searcher import (
    configure_position_searcher,
    configure_region_searcher,
)
from ichnaea.async.app import celery_app
from ichnaea.async.config import (
    init_worker,
    shutdown_worker,
)
from ichnaea.cache import configure_redis
from ichnaea.db import configure_db
from ichnaea.geoip import configure_geoip
from ichnaea.http import configure_http_session
from ichnaea.log import (
    configure_raven,
    configure_stats,
    DebugRavenClient,
    DebugStatsClient,
)
from ichnaea.queue import DataQueue
from ichnaea.tests.base import (
    GEOIP_TEST_FILE,
    TEST_CONFIG,
)
from ichnaea.webapp.config import main

REDIS_URI = os.environ.get('REDIS_URI')
SQLURI = os.environ.get('SQLURI')


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

    yield None

    # Print memory leaks.
    if gc.garbage:  # pragma: no cover
        print('Uncollectable objects found:')
        for obj in gc.garbage:
            print(obj)


@pytest.fixture(scope='session')
def database():
    # Make sure all models are imported.
    from ichnaea import models  # NOQA

    # Setup clean database tables.
    from ichnaea.tests.base import DBTestCase
    DBTestCase.setup_database()


@pytest.yield_fixture(scope='session')
def global_db_rw(request, database):
    db = configure_db(SQLURI)
    yield db
    db.close()


@pytest.yield_fixture(scope='class')
def db_rw(request, global_db_rw):
    request.cls.db_rw = db = global_db_rw
    yield db


@pytest.yield_fixture(scope='session')
def global_db_ro(request, database):
    db = configure_db(SQLURI)
    yield db
    db.close()


@pytest.yield_fixture(scope='class')
def db_ro(request, global_db_ro):
    request.cls.db_ro = db = global_db_ro
    yield db


@pytest.yield_fixture(scope='session')
def global_raven_client(request):
    raven_client = configure_raven(
        None, transport='sync', _client=DebugRavenClient())
    yield raven_client


@pytest.yield_fixture(scope='class')
def raven_client(request, global_raven_client):
    request.cls.raven_client = raven_client = global_raven_client
    yield raven_client


@pytest.yield_fixture(scope='function')
def raven(raven_client):
    yield raven_client
    messages = [msg['message'] for msg in raven_client.msgs]
    raven_client._clear()
    assert not messages


@pytest.yield_fixture(scope='class')
def global_stats_client(request):
    stats_client = configure_stats(
        None, _client=DebugStatsClient(tag_support=True))
    yield stats_client
    stats_client.close()


@pytest.yield_fixture(scope='class')
def stats_client(request, global_stats_client):
    request.cls.stats_client = stats_client = global_stats_client
    yield stats_client


@pytest.yield_fixture(scope='function')
def stats(stats_client):
    yield stats_client
    stats_client._clear()


@pytest.yield_fixture(scope='session')
def global_http_session(request):
    http_session = configure_http_session(size=1)
    yield http_session
    http_session.close()


@pytest.yield_fixture(scope='class')
def http_session(request, global_http_session):
    request.cls.http_session = http_session = global_http_session
    yield http_session


@pytest.yield_fixture(scope='class')
def geoip_db(request, raven_client):
    request.cls.geoip_db = geoip_db = configure_geoip(
        GEOIP_TEST_FILE, mode=MODE_AUTO, raven_client=raven_client)
    yield geoip_db
    geoip_db.close()


@pytest.yield_fixture(scope='session')
def global_redis_client(request):
    redis_client = configure_redis(REDIS_URI)
    yield redis_client
    redis_client.close()


@pytest.yield_fixture(scope='class')
def redis_client(request, global_redis_client):
    request.cls.redis_client = redis_client = global_redis_client
    yield redis_client


@pytest.yield_fixture(scope='function')
def redis(redis_client):
    yield redis_client
    redis_client.flushdb()


@pytest.yield_fixture(scope='class')
def data_queues(request, redis_client):
    request.cls.data_queues = data_queues = {
        'update_incoming': DataQueue('update_incoming', redis_client,
                                     batch=100, compress=True),
    }
    yield data_queues


@pytest.yield_fixture(scope='class')
def position_searcher(request, geoip_db, raven_client,
                      redis_client, stats_client, data_queues):
    request.cls.position_searcher = searcher = configure_position_searcher(
        geoip_db=geoip_db, raven_client=raven_client,
        redis_client=redis_client, stats_client=stats_client,
        data_queues=data_queues)
    yield searcher


@pytest.yield_fixture(scope='class')
def region_searcher(request, geoip_db, raven_client,
                    redis_client, stats_client, data_queues):
    request.cls.region_searcher = searcher = configure_region_searcher(
        geoip_db=geoip_db, raven_client=raven_client,
        redis_client=redis_client, stats_client=stats_client,
        data_queues=data_queues)
    yield searcher


@pytest.yield_fixture(scope='class')
def app(request, db_rw, db_ro, geoip_db, http_session, raven_client,
        redis_client, stats_client, position_searcher, region_searcher):
    wsgiapp = main(
        TEST_CONFIG,
        _db_rw=db_rw,
        _db_ro=db_ro,
        _geoip_db=geoip_db,
        _http_session=http_session,
        _raven_client=raven_client,
        _redis_client=redis_client,
        _stats_client=stats_client,
        _position_searcher=position_searcher,
        _region_searcher=region_searcher,
    )
    request.cls.app = app = webtest.TestApp(wsgiapp)
    yield app


@pytest.yield_fixture(scope='class')
def celery(request, db_rw, geoip_db, raven_client,
           redis_client, stats_client):
    request.cls.celery_app = celery_app
    celery_app.app_config = TEST_CONFIG
    celery_app.settings = TEST_CONFIG.asdict()
    init_worker(
        celery_app,
        _db_rw=db_rw,
        _geoip_db=geoip_db,
        _raven_client=raven_client,
        _redis_client=redis_client,
        _stats_client=stats_client)
    yield celery_app
    shutdown_worker(celery_app)
