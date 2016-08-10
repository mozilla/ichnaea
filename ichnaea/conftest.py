import gc
import os
import warnings

from alembic import command
from alembic.config import Config as AlembicConfig
from maxminddb.const import MODE_AUTO
import pytest
from sqlalchemy import (
    event,
    inspect,
    text,
)
import webtest

from ichnaea.api.locate.searcher import (
    configure_position_searcher,
    configure_region_searcher,
)
from ichnaea.async.app import celery_app
from ichnaea.async.config import (
    init_worker,
    shutdown_worker as shutdown_celery,
)
from ichnaea.cache import configure_redis
from ichnaea.config import (
    DB_RW_URI,
    read_config,
)
from ichnaea.db import (
    configure_rw_db,
    configure_ro_db,
)
from ichnaea.geocode import GEOCODER
from ichnaea.geoip import (
    CITY_RADII,
    configure_geoip,
)
from ichnaea.http import configure_http_session
from ichnaea.log import (
    configure_raven,
    configure_stats,
    DebugRavenClient,
    DebugStatsClient,
)
from ichnaea.models import (
    _Model,
    ApiKey,
)
from ichnaea.queue import DataQueue
from ichnaea.tests import DATA_DIRECTORY
from ichnaea.webapp.config import (
    main,
    shutdown_worker as shutdown_app,
)

# Module global to hold active session, used by factory-boy
SESSION = {}

TEST_CONFIG = read_config(filename=os.path.join(DATA_DIRECTORY, 'test.ini'))

GB_LAT = 51.5
GB_LON = -0.1
GB_MCC = 234
GB_MNC = 30

GEOIP_DATA = {
    'London': {
        'city': True,
        'region_code': 'GB',
        'region_name': 'United Kingdom',
        'ip': '81.2.69.192',
        'latitude': 51.5142,
        'longitude': -0.0931,
        'radius': CITY_RADII[2643743],
        'region_radius': GEOCODER.region_max_radius('GB'),
        'score': 0.8,
    },
    'London2': {
        'city': True,
        'region_code': 'GB',
        'region_name': 'United Kingdom',
        'ip': '81.2.69.144',
        'latitude': 51.5142,
        'longitude': -0.0931,
        'radius': 3000.0,
        'region_radius': GEOCODER.region_max_radius('GB'),
        'score': 0.8,
    },
    'Bhutan': {
        'city': False,
        'region_code': 'BT',
        'region_name': 'Bhutan',
        'ip': '67.43.156.1',
        'latitude': 27.5,
        'longitude': 90.5,
        'radius': GEOCODER.region_max_radius('BT'),
        'region_radius': GEOCODER.region_max_radius('BT'),
        'score': 0.9,
    },
}

ALEMBIC_CFG = AlembicConfig()
ALEMBIC_CFG.set_section_option(
    'alembic', 'script_location', 'alembic')
ALEMBIC_CFG.set_section_option(
    'alembic', 'sqlalchemy.url', DB_RW_URI)
ALEMBIC_CFG.set_section_option(
    'alembic', 'sourceless', 'true')


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


def setup_tables(engine):
    with engine.connect() as conn:
        trans = conn.begin()
        _Model.metadata.create_all(engine)
        # Now stamp the latest alembic version
        command.stamp(ALEMBIC_CFG, 'head')

        # always add a test API key
        conn.execute(ApiKey.__table__.delete())

        key1 = ApiKey.__table__.insert().values(
            valid_key='test',
            allow_fallback=False, allow_locate=True, allow_transfer=True,
            fallback_name='fall',
            fallback_url='http://127.0.0.1:9/?api',
            fallback_ratelimit=10,
            fallback_ratelimit_interval=60,
            fallback_cache_expire=60,
        )
        conn.execute(key1)
        key2 = ApiKey.__table__.insert().values(
            valid_key='export',
            allow_fallback=False, allow_locate=False, allow_transfer=False)
        conn.execute(key2)

        trans.commit()


def cleanup_tables(engine):
    # reflect and delete all tables, not just those known to
    # our current code version / models
    inspector = inspect(engine)
    with engine.connect() as conn:
        trans = conn.begin()
        names = inspector.get_table_names()
        if names:
            tables = '`' + '`, `'.join(names) + '`'
            conn.execute(text('DROP TABLE %s' % tables))
        trans.commit()


def setup_database():
    db = configure_rw_db()
    engine = db.engine
    cleanup_tables(engine)
    setup_tables(engine)
    db.close()


@pytest.fixture(scope='session')
def database():
    # Make sure all models are imported.
    from ichnaea import models  # NOQA

    # Setup clean database tables.
    setup_database()


@pytest.yield_fixture(scope='session')
def db_rw(database):
    db = configure_rw_db()
    yield db
    db.close()


@pytest.yield_fixture(scope='session')
def db_ro(database):
    db = configure_ro_db()
    yield db
    db.close()


@pytest.yield_fixture(scope='function')
def db_rw_drop_table(db_rw):
    yield db_rw
    setup_tables(db_rw.engine)


@pytest.yield_fixture(scope='function')
def rw_session(db_rw):
    rw_conn = db_rw.engine.connect()
    rw_trans = rw_conn.begin()
    db_rw.session_factory.configure(bind=rw_conn)
    rw_session = db_rw.session()

    yield rw_session

    rw_trans.rollback()
    rw_session.close()
    db_rw.session_factory.configure(bind=None)
    rw_trans.close()
    rw_conn.close()


@pytest.yield_fixture(scope='function')
def ro_session(db_ro):
    ro_conn = db_ro.engine.connect()
    ro_trans = ro_conn.begin()
    db_ro.session_factory.configure(bind=ro_conn)
    ro_session = db_ro.session()

    yield ro_session

    ro_trans.rollback()
    ro_session.close()
    db_ro.session_factory.configure(bind=None)
    ro_trans.close()
    ro_conn.close()


@pytest.yield_fixture(scope='function')
def rw_session_tracker(rw_session):
    """
    This install an event handler into the active session, which
    tracks all SQL statements that are send via the session.

    The yielded checker can be called with an integer argument,
    representing the number of expected SQL statements, for example::

        rw_session_tracker(0)

    would only succeed if no SQL statements where made.
    """

    db_events = []

    def scoped_conn_event_handler(calls):
        def conn_event_handler(**kw):  # pragma: no cover
            calls.append((kw['statement'], kw['parameters']))
        return conn_event_handler

    handler = scoped_conn_event_handler(db_events)
    event.listen(rw_session.bind,
                 'before_cursor_execute',
                 handler, named=True)

    def checker(num=None):
        if num is not None:
            assert len(db_events) == num

    yield checker

    event.remove(rw_session.bind, 'before_cursor_execute', handler)


@pytest.yield_fixture(scope='function')
def ro_session_tracker(ro_session):
    """
    This install an event handler into the active session, which
    tracks all SQL statements that are send via the session.

    The yielded checker can be called with an integer argument,
    representing the number of expected SQL statements, for example::

        ro_session_tracker(0)

    would only succeed if no SQL statements where made.
    """

    db_events = []

    def scoped_conn_event_handler(calls):
        def conn_event_handler(**kw):
            calls.append((kw['statement'], kw['parameters']))
        return conn_event_handler

    handler = scoped_conn_event_handler(db_events)
    event.listen(ro_session.bind,
                 'before_cursor_execute',
                 handler, named=True)

    def checker(num=None):
        if num is not None:
            assert len(db_events) == num

    yield checker

    event.remove(ro_session.bind, 'before_cursor_execute', handler)


@pytest.yield_fixture(scope='function')
def session(rw_session):
    # Set the global session context for factory-boy.
    SESSION['default'] = rw_session
    yield rw_session
    del SESSION['default']


@pytest.yield_fixture(scope='session')
def data_queues(redis_client):
    data_queues = {
        'update_incoming': DataQueue('update_incoming', redis_client,
                                     batch=100, compress=True),
        'transfer_incoming': DataQueue('transfer_incoming', redis_client,
                                       batch=100, compress=True),
    }
    yield data_queues


@pytest.yield_fixture(scope='session')
def geoip_data():
    yield GEOIP_DATA


@pytest.yield_fixture(scope='session')
def geoip_db(raven_client):
    geoip_db = configure_geoip(mode=MODE_AUTO, raven_client=raven_client)
    yield geoip_db
    geoip_db.close()


@pytest.yield_fixture(scope='session')
def http_session():
    http_session = configure_http_session(size=1)
    yield http_session
    http_session.close()


@pytest.yield_fixture(scope='session')
def raven_client():
    raven_client = configure_raven(
        None, transport='sync', _client=DebugRavenClient())
    yield raven_client


@pytest.yield_fixture(scope='function')
def raven(raven_client):
    yield raven_client
    messages = [msg['message'] for msg in raven_client.msgs]
    raven_client._clear()
    assert not messages


@pytest.yield_fixture(scope='session')
def redis_client():
    redis_client = configure_redis()
    yield redis_client
    redis_client.close()


@pytest.yield_fixture(scope='function')
def redis(redis_client):
    yield redis_client
    redis_client.flushdb()


@pytest.yield_fixture(scope='session')
def stats_client():
    stats_client = configure_stats(
        None, _client=DebugStatsClient(tag_support=True))
    yield stats_client
    stats_client.close()


@pytest.yield_fixture(scope='function')
def stats(stats_client):
    yield stats_client
    stats_client._clear()


@pytest.yield_fixture(scope='session')
def position_searcher(data_queues, geoip_db,
                      raven_client, redis_client, stats_client):
    searcher = configure_position_searcher(
        geoip_db=geoip_db, raven_client=raven_client,
        redis_client=redis_client, stats_client=stats_client,
        data_queues=data_queues)
    yield searcher


@pytest.yield_fixture(scope='session')
def region_searcher(data_queues, geoip_db,
                    raven_client, redis_client, stats_client):
    searcher = configure_region_searcher(
        geoip_db=geoip_db, raven_client=raven_client,
        redis_client=redis_client, stats_client=stats_client,
        data_queues=data_queues)
    yield searcher


@pytest.yield_fixture(scope='session')
def global_app(db_ro, geoip_db, http_session,
               raven_client, redis_client, stats_client,
               position_searcher, region_searcher):
    wsgiapp = main(
        TEST_CONFIG,
        _db_ro=db_ro,
        _geoip_db=geoip_db,
        _http_session=http_session,
        _raven_client=raven_client,
        _redis_client=redis_client,
        _stats_client=stats_client,
        _position_searcher=position_searcher,
        _region_searcher=region_searcher,
    )
    app = webtest.TestApp(wsgiapp)
    yield app
    shutdown_app(app.app)


@pytest.yield_fixture(scope='function')
def app(global_app, raven, redis, ro_session, stats):
    yield global_app


@pytest.yield_fixture(scope='session')
def global_celery(db_rw, geoip_db,
                  raven_client, redis_client, stats_client):
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
    shutdown_celery(celery_app)


@pytest.yield_fixture(scope='function')
def celery(global_celery, raven, redis, rw_session, stats):
    yield global_celery
