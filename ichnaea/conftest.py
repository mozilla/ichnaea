from __future__ import absolute_import

import gc
import warnings

from alembic import command
from maxminddb.const import MODE_AUTO
import pytest
from _pytest.monkeypatch import MonkeyPatch
from sqlalchemy import event, inspect, text
from sqlalchemy.exc import ProgrammingError
import webtest

from ichnaea.api.key import API_CACHE
from ichnaea.api.locate.searcher import (
    configure_position_searcher,
    configure_region_searcher,
)
from ichnaea.async.app import celery_app
from ichnaea.async.config import init_worker, shutdown_worker as shutdown_celery
from ichnaea.cache import configure_redis
from ichnaea.db import configure_db, create_db, get_alembic_config
from ichnaea.geocode import GEOCODER
from ichnaea.geoip import CITY_RADII, configure_geoip
from ichnaea.http import configure_http_session
from ichnaea.log import configure_raven, configure_stats
from ichnaea.models import _Model
from ichnaea.queue import DataQueue
from ichnaea.webapp.config import main, shutdown_worker as shutdown_app

# Module global to hold active session, used by factory-boy
SESSION = {}

GB_LAT = 51.5
GB_LON = -0.1
GB_MCC = 234
GB_MNC = 30

GEOIP_DATA = {
    "London": {
        "city": True,
        "region_code": "GB",
        "region_name": "United Kingdom",
        "ip": "81.2.69.192",
        "latitude": 51.5142,
        "longitude": -0.0931,
        "radius": CITY_RADII[2643743],
        "region_radius": GEOCODER.region_max_radius("GB"),
        "score": 0.8,
    },
    "London2": {
        "city": True,
        "region_code": "GB",
        "region_name": "United Kingdom",
        "ip": "81.2.69.144",
        "latitude": 51.5142,
        "longitude": -0.0931,
        "radius": 3000.0,
        "region_radius": GEOCODER.region_max_radius("GB"),
        "score": 0.8,
    },
    "Bhutan": {
        "city": False,
        "region_code": "BT",
        "region_name": "Bhutan",
        "ip": "67.43.156.1",
        "latitude": 27.5,
        "longitude": 90.5,
        "radius": GEOCODER.region_max_radius("BT"),
        "region_radius": GEOCODER.region_max_radius("BT"),
        "score": 0.9,
    },
}


@pytest.fixture(scope="session")
def monkeysession(request):
    mp = MonkeyPatch()
    request.addfinalizer(mp.undo)
    return mp


@pytest.fixture(scope="session", autouse=True)
def package():
    # We do this here as early as possible in tests.
    # We only do it in tests, as the real celery processes should
    # run without the monkey patches applied. The gunicorn arbiter
    # patches its worker processes itself.
    from gevent import monkey

    monkey.patch_all()

    # Enable all warnings in test mode.
    warnings.resetwarnings()
    warnings.simplefilter("default")

    # Look for memory leaks.
    gc.set_debug(gc.DEBUG_UNCOLLECTABLE)

    yield None

    # Print memory leaks.
    if gc.garbage:
        print("Uncollectable objects found:")
        for obj in gc.garbage:
            print(obj)


def _setup_table_contents(conn):
    # Avoid import cycle
    from ichnaea.tests.factories import ApiKeyFactory

    conn.execute(text("DELETE FROM api_key"))
    conn.execute(text("DELETE FROM export_config"))
    key = ApiKeyFactory.build(valid_key="test")
    state = dict(key.__dict__)
    del state["_sa_instance_state"]
    conn.execute(key.__table__.insert().values(state))


def setup_tables(engine):
    alembic_cfg = get_alembic_config()
    with engine.connect() as conn:
        with conn.begin() as trans:
            # Now stamp the latest alembic version
            command.stamp(alembic_cfg, "base")
            command.upgrade(alembic_cfg, "head")
            _setup_table_contents(conn)
            trans.commit()


def cleanup_tables(engine):
    # reflect and delete all tables, not just those known to our current code
    # version / models
    inspector = inspect(engine)
    with engine.connect() as conn:
        with conn.begin() as trans:
            names = inspector.get_table_names()
            if names:
                tables = "`" + "`, `".join(names) + "`"
                conn.execute(text("DROP TABLE %s" % tables))
            trans.commit()


def setup_database():
    # Create it if it doesn't exist
    try:
        create_db()
    except ProgrammingError:
        pass

    # Clean up the tables and set them up
    db = configure_db("ddl")
    cleanup_tables(db.engine)
    setup_tables(db.engine)
    db.close()


@pytest.fixture(scope="session")
def database():
    # Make sure all models are imported.
    from ichnaea import models  # noqa

    # Setup clean database tables.
    setup_database()


@pytest.fixture(scope="session")
def db(database):
    db = configure_db("rw")
    yield db
    db.close()


@pytest.fixture(scope="function")
def clean_db(db):
    yield db
    # drop and recreate all tables
    setup_database()


@pytest.fixture(scope="session")
def sync_db(database):
    db = configure_db("rw", transport="sync")
    yield db
    db.close()


@pytest.fixture(scope="function")
def restore_db(db):
    yield db
    # add back missing tables
    with db.engine.connect() as conn:
        with conn.begin() as trans:
            _Model.metadata.create_all(db.engine)
            _setup_table_contents(conn)
            trans.commit()


@pytest.fixture(scope="function")
def session(db):
    with db.engine.connect() as conn:
        with conn.begin() as trans:
            db.session_factory.configure(bind=conn)
            session = db.session()

            # Set the global session context for factory-boy.
            SESSION["default"] = session
            yield session
            del SESSION["default"]

            trans.rollback()
            session.close()
            db.session_factory.configure(bind=db.engine)

    API_CACHE.clear()


@pytest.fixture(scope="function")
def sync_session(sync_db):
    with sync_db.engine.connect() as conn:
        with conn.begin() as trans:
            sync_db.session_factory.configure(bind=conn)
            session = sync_db.session()

            # Set the global session context for factory-boy.
            SESSION["default"] = session
            yield session
            del SESSION["default"]

            trans.rollback()
            session.close()
            sync_db.session_factory.configure(bind=sync_db.engine)

    API_CACHE.clear()


@pytest.fixture(scope="function")
def session_tracker(session):
    """
    This install an event handler into the active session, which
    tracks all SQL statements that are send via the session.

    The yielded checker can be called with an integer argument,
    representing the number of expected SQL statements, for example::

        session_tracker(0)

    would only succeed if no SQL statements where made.
    """

    db_events = []

    def scoped_conn_event_handler(calls):
        def conn_event_handler(**kw):
            calls.append((kw["statement"], kw["parameters"]))

        return conn_event_handler

    handler = scoped_conn_event_handler(db_events)
    event.listen(session.bind, "before_cursor_execute", handler, named=True)

    def checker(num=None):
        if num is not None:
            assert len(db_events) == num

    yield checker

    event.remove(session.bind, "before_cursor_execute", handler)


@pytest.fixture(scope="session")
def data_queues(redis_client):
    data_queues = {
        "update_incoming": DataQueue(
            "update_incoming", redis_client, batch=100, compress=True
        )
    }
    yield data_queues


@pytest.fixture(scope="session")
def geoip_data():
    yield GEOIP_DATA


@pytest.fixture(scope="session")
def geoip_db(raven_client):
    geoip_db = configure_geoip(mode=MODE_AUTO, raven_client=raven_client)
    yield geoip_db
    geoip_db.close()


@pytest.fixture(scope="session")
def http_session():
    http_session = configure_http_session(size=1)
    yield http_session
    http_session.close()


@pytest.fixture(scope="session")
def raven_client():
    raven_client = configure_raven(transport="sync")
    yield raven_client


@pytest.fixture(scope="function")
def raven(raven_client):
    yield raven_client
    messages = [msg["message"] for msg in raven_client.msgs]
    raven_client._clear()
    assert not messages


@pytest.fixture(scope="session")
def redis_client():
    redis_client = configure_redis()
    yield redis_client
    redis_client.close()


@pytest.fixture(scope="function")
def redis(redis_client):
    yield redis_client
    redis_client.flushdb()


@pytest.fixture(scope="session")
def stats_client():
    stats_client = configure_stats()
    yield stats_client
    stats_client.close()


@pytest.fixture(scope="function")
def stats(stats_client):
    yield stats_client
    stats_client._clear()


@pytest.fixture(scope="session")
def position_searcher(data_queues, geoip_db, raven_client, redis_client, stats_client):
    searcher = configure_position_searcher(
        geoip_db=geoip_db,
        raven_client=raven_client,
        redis_client=redis_client,
        stats_client=stats_client,
        data_queues=data_queues,
    )
    yield searcher


@pytest.fixture(scope="session")
def region_searcher(data_queues, geoip_db, raven_client, redis_client, stats_client):
    searcher = configure_region_searcher(
        geoip_db=geoip_db,
        raven_client=raven_client,
        redis_client=redis_client,
        stats_client=stats_client,
        data_queues=data_queues,
    )
    yield searcher


@pytest.fixture(scope="session")
def map_config(monkeysession):
    tiles_url = "http://127.0.0.1:9/static/tiles/{z}/{x}/{y}.png"
    monkeysession.setattr("ichnaea.content.views.MAP_TILES_URL", tiles_url)


@pytest.fixture(scope="session")
def global_app(
    db,
    geoip_db,
    http_session,
    map_config,
    raven_client,
    redis_client,
    stats_client,
    position_searcher,
    region_searcher,
):
    wsgiapp = main(
        _db=db,
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


@pytest.fixture(scope="function")
def app(global_app, raven, redis, session, stats):
    yield global_app


@pytest.fixture(scope="session")
def global_celery(db, geoip_db, raven_client, redis_client, stats_client):
    init_worker(
        celery_app,
        _db=db,
        _geoip_db=geoip_db,
        _raven_client=raven_client,
        _redis_client=redis_client,
        _stats_client=stats_client,
    )
    yield celery_app
    shutdown_celery(celery_app)


@pytest.fixture(scope="function")
def celery(global_celery, raven, redis, session, stats):
    yield global_celery
