from contextlib import contextmanager
import gc
import os
import os.path

from alembic.config import Config
from alembic import command
from maxminddb.const import MODE_AUTO
from sqlalchemy import (
    event,
    inspect,
    text,
)
from webtest import TestApp

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
from ichnaea.config import read_config
from ichnaea.db import configure_db
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
from ichnaea.models import _Model, ApiKey
from ichnaea.queue import DataQueue
from ichnaea.webapp.config import main

# make new unittest API's available under Python 2.6
try:
    from unittest2 import TestCase  # NOQA
except ImportError:
    from unittest import TestCase

TEST_DIRECTORY = os.path.dirname(__file__)
DATA_DIRECTORY = os.path.join(TEST_DIRECTORY, 'data')
GEOIP_TEST_FILE = os.path.join(DATA_DIRECTORY, 'GeoIP2-City-Test.mmdb')
GEOIP_BAD_FILE = os.path.join(
    DATA_DIRECTORY, 'GeoIP2-Connection-Type-Test.mmdb')

SQLURI = os.environ.get('SQLURI')
REDIS_URI = os.environ.get('REDIS_URI')

SESSION = {}

# Some test-data constants

TEST_CONFIG = read_config(filename=os.path.join(DATA_DIRECTORY, 'test.ini'))

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

GB_LAT = 51.5
GB_LON = -0.1
GB_MCC = 234
GB_MNC = 30


def _make_db(uri=SQLURI):
    return configure_db(uri)


def _make_redis(uri=REDIS_URI):
    return configure_redis(uri)


def _make_app(app_config=TEST_CONFIG,
              _db_rw=None, _db_ro=None, _http_session=None, _geoip_db=None,
              _raven_client=None, _redis_client=None, _stats_client=None,
              _position_searcher=None, _region_searcher=None):
    wsgiapp = main(
        app_config,
        _db_rw=_db_rw,
        _db_ro=_db_ro,
        _geoip_db=_geoip_db,
        _http_session=_http_session,
        _raven_client=_raven_client,
        _redis_client=_redis_client,
        _stats_client=_stats_client,
        _position_searcher=_position_searcher,
        _region_searcher=_region_searcher,
    )
    return TestApp(wsgiapp)


class LogTestCase(TestCase):

    @classmethod
    def setUpClass(cls):
        super(LogTestCase, cls).setUpClass()
        # Use a debug configuration
        cls.raven_client = configure_raven(
            None, transport='sync', _client=DebugRavenClient())
        cls.stats_client = configure_stats(
            None, _client=DebugStatsClient(tag_support=True))

    @classmethod
    def tearDownClass(cls):
        super(LogTestCase, cls).tearDownClass()
        del cls.raven_client
        cls.stats_client.close()
        del cls.stats_client

    def setUp(self):
        super(LogTestCase, self).setUp()
        self._unexpected_errors = []

    def tearDown(self):
        super(LogTestCase, self).tearDown()
        self.assert_no_unexpected_raven_errors()
        del self._unexpected_errors
        self.raven_client._clear()
        self.stats_client._clear()

    def find_stats_messages(self, msg_type, msg_name,
                            msg_value=None, msg_tags=(), _client=None):
        data = {
            'counter': [],
            'timer': [],
            'gauge': [],
            'histogram': [],
            'meter': [],
            'set': [],
        }
        if _client is None:
            client = self.stats_client
        else:
            client = _client

        for msg in client.msgs:
            tags = ()
            if '|#' in msg:
                parts = msg.split('|#')
                tags = parts[-1].split(',')
                msg = parts[0]
            suffix = msg.split('|')[-1]
            name, value = msg.split('|')[0].split(':')
            value = int(value)
            if suffix == 'g':
                data['gauge'].append((name, value, tags))
            elif suffix == 'ms':
                data['timer'].append((name, value, tags))
            elif suffix.startswith('c'):
                data['counter'].append((name, value, tags))
            elif suffix == 'h':
                data['histogram'].append((name, value, tags))
            elif suffix == 'm':
                data['meter'].append((name, value, tags))
            elif suffix == 's':
                data['set'].append((name, value, tags))

        result = []
        for msg in data.get(msg_type):
            if msg[0] == msg_name:
                if msg_value is None or msg[1] == msg_value:
                    if not msg_tags or msg[2] == msg_tags:
                        result.append((msg[0], msg[1], msg[2]))
        return result

    def check_raven(self, expected=None):
        """Checks the raven message stream looking for the expected messages.

        The expected argument should be a list of either names or tuples.

        If it is a tuple, it should be a tuple of name and an expected count.

        The names are matched via startswith against the captured exception
        messages.
        """
        msgs = self.raven_client.msgs
        found_msgs = [msg['message'] for msg in msgs]
        matched_msgs = []
        if expected is None:
            expected = ()
        for exp in expected:
            count = 1
            name = exp
            if isinstance(exp, tuple):
                name, count = exp
            matches = [found for found in found_msgs if found.startswith(name)]
            matched_msgs.extend(matches)
            self.assertEqual(len(matches), count, found_msgs)
        self._unexpected_errors = [msg for msg in msgs
                                   if msg['message'] not in matched_msgs]

    def assert_no_unexpected_raven_errors(self):
        self.assertEqual(len(self._unexpected_errors), 0,
                         self._unexpected_errors)

    def check_stats(self, _client=None, total=None, **kw):
        """Checks a partial specification of messages to be found in
        the stats message stream.
        """
        if _client is None:
            client = self.stats_client
        else:
            client = _client
        if total is not None:
            self.assertEqual(total, len(client.msgs), client.msgs)

        for (msg_type, preds) in kw.items():
            for pred in preds:
                match = 1
                value = None
                tags = ()
                if isinstance(pred, str):
                    name = pred
                elif isinstance(pred, tuple):
                    if len(pred) == 2:
                        (name, match) = pred
                        if isinstance(match, list):
                            tags = match
                            match = 1
                    elif len(pred) == 3:
                        (name, match, value) = pred
                        if isinstance(value, list):
                            tags = value
                            value = None
                    elif len(pred) == 4:
                        (name, match, value, tags) = pred
                    else:
                        raise TypeError('wanted 2, 3 or 4 tuple, got %s'
                                        % type(pred))
                else:
                    raise TypeError('wanted str or tuple, got %s'
                                    % type(pred))
                msgs = self.find_stats_messages(
                    msg_type, name, value, tags, _client=client)
                if isinstance(match, int):
                    self.assertEqual(match, len(msgs),
                                     msg='%s %s not found' % (msg_type, name))


class DBTestCase(LogTestCase):
    # Inspired by a blog post:
    # http://sontek.net/blog/detail/writing-tests-for-pyramid-and-sqlalchemy

    default_session = 'db_rw_session'
    track_connection_events = False

    @contextmanager
    def db_call_checker(self):
        try:
            self.setup_db_event_tracking()
            yield self.check_db_calls
        finally:
            self.teardown_db_event_tracking()

    def check_db_calls(self, rw=None, ro=None):
        if rw is not None:
            events = self.db_events['rw']['calls']
            self.assertEqual(len(events), rw, events)
        if ro is not None:
            events = self.db_events['ro']['calls']
            self.assertEqual(len(events), ro, events)

    def reset_db_event_tracking(self):
        self.db_events = {
            'rw': {'calls': [], 'handler': None},
            'ro': {'calls': [], 'handler': None},
        }

    def setup_db_event_tracking(self):
        self.reset_db_event_tracking()

        def scoped_conn_event_handler(calls):
            def conn_event_handler(**kw):
                calls.append((kw['statement'], kw['parameters']))
            return conn_event_handler

        rw_handler = scoped_conn_event_handler(self.db_events['rw']['calls'])
        self.db_events['rw']['handler'] = rw_handler
        event.listen(self.rw_conn, 'before_cursor_execute',
                     rw_handler, named=True)

        ro_handler = scoped_conn_event_handler(self.db_events['ro']['calls'])
        self.db_events['ro']['handler'] = ro_handler
        event.listen(self.ro_conn, 'before_cursor_execute',
                     ro_handler, named=True)

    def teardown_db_event_tracking(self):
        event.remove(self.ro_conn, 'before_cursor_execute',
                     self.db_events['ro']['handler'])
        event.remove(self.rw_conn, 'before_cursor_execute',
                     self.db_events['rw']['handler'])
        self.reset_db_event_tracking()

    def setUp(self):
        super(DBTestCase, self).setUp()
        self.rw_conn = self.db_rw.engine.connect()
        self.rw_trans = self.rw_conn.begin()
        self.db_rw.session_factory.configure(bind=self.rw_conn)
        self.db_rw_session = self.db_rw.session()
        self.ro_conn = self.db_ro.engine.connect()
        self.ro_trans = self.ro_conn.begin()
        self.db_ro.session_factory.configure(bind=self.ro_conn)
        self.db_ro_session = self.db_ro.session()

        # set up a default session
        default_session = getattr(self, self.default_session)
        setattr(self, 'session', default_session)
        SESSION['default'] = default_session

        if self.track_connection_events:
            self.setup_db_event_tracking()

    def tearDown(self):
        super(DBTestCase, self).tearDown()
        if self.track_connection_events:
            self.teardown_db_event_tracking()

        del SESSION['default']
        del self.session

        self.ro_trans.rollback()
        self.db_ro_session.close()
        del self.db_ro_session
        self.db_ro.session_factory.configure(bind=None)
        self.ro_trans.close()
        del self.ro_trans
        self.ro_conn.close()
        del self.ro_conn
        self.rw_trans.rollback()
        self.db_rw_session.close()
        del self.db_rw_session
        self.db_rw.session_factory.configure(bind=None)
        self.rw_trans.close()
        del self.rw_trans
        self.rw_conn.close()
        del self.rw_conn

    @classmethod
    def setUpClass(cls):
        super(DBTestCase, cls).setUpClass()
        cls.db_rw = _make_db()
        cls.db_ro = _make_db()

    @classmethod
    def tearDownClass(cls):
        super(DBTestCase, cls).tearDownClass()
        cls.db_rw.close()
        del cls.db_rw
        cls.db_ro.close()
        del cls.db_ro

    @classmethod
    def setup_tables(cls, engine):
        with engine.connect() as conn:
            trans = conn.begin()
            _Model.metadata.create_all(engine)
            # Now stamp the latest alembic version
            alembic_cfg = Config()
            alembic_cfg.set_section_option(
                'alembic', 'script_location', 'alembic')
            alembic_cfg.set_section_option(
                'alembic', 'sqlalchemy.url', str(engine.url))
            alembic_cfg.set_section_option(
                'alembic', 'sourceless', 'true')

            command.stamp(alembic_cfg, 'head')

            # always add a test API key
            conn.execute(ApiKey.__table__.delete())

            key1 = ApiKey.__table__.insert().values(
                valid_key='test', allow_fallback=False, allow_locate=True,
                fallback_name='fall',
                fallback_url='http://127.0.0.1:9/?api',
                fallback_ratelimit=10,
                fallback_ratelimit_interval=60,
                fallback_cache_expire=60,
            )
            conn.execute(key1)
            key2 = ApiKey.__table__.insert().values(
                valid_key='export', allow_fallback=False, allow_locate=False)
            conn.execute(key2)

            trans.commit()

    @classmethod
    def cleanup_tables(cls, engine):
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


class HTTPTestCase(object):

    @classmethod
    def setUpClass(cls):
        super(HTTPTestCase, cls).setUpClass()
        cls.http_session = configure_http_session(size=1)

    @classmethod
    def tearDownClass(cls):
        super(HTTPTestCase, cls).tearDownClass()
        cls.http_session.close()
        del cls.http_session


class GeoIPTestCase(LogTestCase):

    geoip_data = GEOIP_DATA

    @classmethod
    def _open_db(cls, filename=None, mode=MODE_AUTO):
        if filename is None:
            filename = GEOIP_TEST_FILE
        return configure_geoip(
            filename, mode=mode, raven_client=cls.raven_client)

    @classmethod
    def setUpClass(cls):
        super(GeoIPTestCase, cls).setUpClass()
        cls.geoip_db = cls._open_db()

    @classmethod
    def tearDownClass(cls):
        super(GeoIPTestCase, cls).tearDownClass()
        cls.geoip_db.close()
        del cls.geoip_db


class RedisTestCase(LogTestCase):

    @classmethod
    def setUpClass(cls):
        super(RedisTestCase, cls).setUpClass()
        cls.redis_client = _make_redis()

    @classmethod
    def tearDownClass(cls):
        super(RedisTestCase, cls).tearDownClass()
        cls.redis_client.close()
        del cls.redis_client

    def tearDown(self):
        super(RedisTestCase, self).tearDown()
        self.redis_client.flushdb()


class ConnectionTestCase(DBTestCase, GeoIPTestCase,
                         HTTPTestCase, RedisTestCase):

    @classmethod
    def _configure_data_queues(cls):
        return {
            'update_incoming': DataQueue('update_incoming', cls.redis_client,
                                         batch=100, compress=True),
        }

    @classmethod
    def setUpClass(cls):
        super(ConnectionTestCase, cls).setUpClass()
        cls.data_queues = cls._configure_data_queues()

    @classmethod
    def tearDownClass(cls):
        super(ConnectionTestCase, cls).tearDownClass()
        del cls.data_queues


class APITestCase(ConnectionTestCase):

    @classmethod
    def setUpClass(cls):
        super(APITestCase, cls).setUpClass()
        for name, func in (('position_searcher', configure_position_searcher),
                           ('region_searcher', configure_region_searcher)):
            searcher = func(
                geoip_db=cls.geoip_db, raven_client=cls.raven_client,
                redis_client=cls.redis_client, stats_client=cls.stats_client,
                data_queues=cls.data_queues)
            setattr(cls, name, searcher)

    @classmethod
    def tearDownClass(cls):
        super(APITestCase, cls).tearDownClass()
        del cls.position_searcher
        del cls.region_searcher


class AppTestCase(APITestCase):

    default_session = 'db_ro_session'

    @classmethod
    def setUpClass(cls):
        super(AppTestCase, cls).setUpClass()
        cls.app = _make_app(app_config=TEST_CONFIG,
                            _db_rw=cls.db_rw,
                            _db_ro=cls.db_ro,
                            _http_session=cls.http_session,
                            _geoip_db=cls.geoip_db,
                            _raven_client=cls.raven_client,
                            _redis_client=cls.redis_client,
                            _stats_client=cls.stats_client,
                            _position_searcher=cls.position_searcher,
                            _region_searcher=cls.region_searcher)

    @classmethod
    def tearDownClass(cls):
        super(AppTestCase, cls).tearDownClass()
        del cls.app


class CeleryTestCase(ConnectionTestCase):

    @classmethod
    def setUpClass(cls):
        super(CeleryTestCase, cls).setUpClass()
        cls.celery_app = celery_app
        celery_app.app_config = TEST_CONFIG
        celery_app.settings = TEST_CONFIG.asdict()
        init_worker(
            celery_app,
            _db_rw=cls.db_rw,
            _geoip_db=cls.geoip_db,
            _raven_client=cls.raven_client,
            _redis_client=cls.redis_client,
            _stats_client=cls.stats_client)

    @classmethod
    def tearDownClass(cls):
        super(CeleryTestCase, cls).tearDownClass()
        shutdown_worker(celery_app)
        del cls.celery_app


class CeleryAppTestCase(AppTestCase, CeleryTestCase):
    default_session = 'db_rw_session'


def setup_package(module):
    # look for memory leaks
    gc.set_debug(gc.DEBUG_UNCOLLECTABLE)

    # make sure all models are imported
    from ichnaea.models import base  # NOQA
    from ichnaea.models import content  # NOQA
    db = _make_db()
    engine = db.engine
    DBTestCase.cleanup_tables(engine)
    DBTestCase.setup_tables(engine)
    db.close()


def teardown_package(module):
    if gc.garbage:
        print('Uncollectable objects found:')
        for obj in gc.garbage:
            print(obj)
