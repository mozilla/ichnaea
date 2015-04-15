from contextlib import contextmanager
import os
import os.path

from alembic.config import Config
from alembic import command
from maxminddb.const import MODE_AUTO
from sqlalchemy import (
    event,
    inspect,
)
from sqlalchemy.schema import (
    DropTable,
    MetaData,
    Table,
)
from unittest2 import TestCase
from webtest import TestApp

from ichnaea.async.app import celery_app
from ichnaea.async.config import init_worker
from ichnaea.cache import redis_client
from ichnaea.config import DummyConfig
from ichnaea.constants import GEOIP_CITY_ACCURACY
from ichnaea.db import Database
from ichnaea.geocalc import maximum_country_radius
from ichnaea.geoip import configure_geoip
from ichnaea.log import (
    configure_raven,
    configure_stats,
    DebugRavenClient,
    DebugStatsClient,
)
from ichnaea.models import _Model, ApiKey
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
SQL_BASE_STRUCTURE = os.path.join(DATA_DIRECTORY, 'base_structure.sql')

SQLURI = os.environ.get('SQLURI')
REDIS_URI = os.environ.get('REDIS_URI', 'redis://localhost:6379/1')

SESSION = {}

# Some test-data constants

TEST_CONFIG = DummyConfig({
    'ichnaea': {
        'assets_url': 'http://127.0.0.1:7001/static/',
        's3_backup_bucket': 'localhost.bucket',
        's3_assets_bucket': 'localhost.bucket',
        'ocid_url': 'http://127.0.0.1:9/downloads/',
        'ocid_apikey': 'xxxxxxxx-yyyy-xxxx-yyyy-xxxxxxxxxxxx',
    },
    'export:test': {
        'url': None,
        'source_apikey': 'export',
        'batch': '3',
    },
})

GEOIP_DATA = {
    'London': {
        'city': True,
        'country_code': 'GB',
        'country_name': 'United Kingdom',
        'ip': '81.2.69.192',
        'latitude': 51.5142,
        'longitude': -0.0931,
        'accuracy': GEOIP_CITY_ACCURACY,
    },
    'Bhutan': {
        'city': False,
        'country_code': 'BT',
        'country_name': 'Bhutan',
        'ip': '67.43.156.1',
        'latitude': 27.5,
        'longitude': 90.5,
        'accuracy': maximum_country_radius('BT'),
    },
}

CANADA_MCC = 302
USA_MCC = 310
ATT_MNC = 150
FREMONT_LAT = 37.5079
FREMONT_LON = -121.96

BRAZIL_MCC = 724
VIVO_MNC = 11
SAO_PAULO_LAT = -23.54
SAO_PAULO_LON = -46.64
PORTO_ALEGRE_LAT = -30.032
PORTO_ALEGRE_LON = -51.22

FRANCE_MCC = 208
VIVENDI_MNC = 10
PARIS_LAT = 48.8568
PARIS_LON = 2.3508

BHUTAN_MCC = 402

GB_LAT = 51.5
GB_LON = -0.1
GB_MCC = 234
GB_MNC = 30


def _make_db(uri=SQLURI):
    return Database(uri)


def _make_redis(uri=REDIS_URI):
    return redis_client(uri)


def _make_app(app_config=TEST_CONFIG,
              _db_rw=None, _db_ro=None, _geoip_db=None,
              _raven_client=None, _redis_client=None, _stats_client=None):
    wsgiapp = main(
        {},
        app_config,
        _db_rw=_db_rw,
        _db_ro=_db_ro,
        _geoip_db=_geoip_db,
        _raven_client=_raven_client,
        _redis_client=_redis_client,
        _stats_client=_stats_client)
    return TestApp(wsgiapp)


def find_msg(msgs, msg_type, field_value, field_name='name'):
    return [m for m in msgs if m.type == msg_type and
            [f for f in m.fields if f.name == field_name and
             f.value_string == [field_value]]]


def scoped_conn_event_handler(calls):
    def conn_event_handler(**kw):
        calls.append((kw['statement'], kw['parameters']))
    return conn_event_handler


class DBIsolation(object):
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

        self.db_events['rw']['handler'] = handler = \
            scoped_conn_event_handler(self.db_events['rw']['calls'])
        event.listen(self.rw_conn, 'before_cursor_execute',
                     handler, named=True)

        self.db_events['ro']['handler'] = handler = \
            scoped_conn_event_handler(self.db_events['ro']['calls'])
        event.listen(self.ro_conn, 'before_cursor_execute',
                     handler, named=True)

    def teardown_db_event_tracking(self):
        event.remove(self.ro_conn, 'before_cursor_execute',
                     self.db_events['ro']['handler'])
        event.remove(self.rw_conn, 'before_cursor_execute',
                     self.db_events['rw']['handler'])
        self.reset_db_event_tracking()

    def setup_session(self):
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

    def teardown_session(self):
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
    def setup_engine(cls):
        cls.db_rw = _make_db()
        cls.db_ro = _make_db()

    @classmethod
    def teardown_engine(cls):
        cls.db_rw.engine.pool.dispose()
        del cls.db_rw
        cls.db_ro.engine.pool.dispose()
        del cls.db_ro

    @classmethod
    def setup_tables(cls, engine):
        with engine.connect() as conn:
            trans = conn.begin()
            _Model.metadata.create_all(engine)
            # Now stamp the latest alembic version
            alembic_cfg = Config()
            alembic_cfg.set_section_option('alembic',
                                           'script_location',
                                           'alembic')
            alembic_cfg.set_section_option('alembic',
                                           'sqlalchemy.url',
                                           str(engine.url))

            command.stamp(alembic_cfg, "head")
            trans.commit()

    @classmethod
    def cleanup_tables(cls, engine):
        # reflect and delete all tables, not just those known to
        # our current code version / models
        metadata = MetaData()
        inspector = inspect(engine)
        tables = []
        with engine.connect() as conn:
            trans = conn.begin()
            for t in inspector.get_table_names():
                tables.append(Table(t, metadata))
            for t in tables:
                conn.execute(DropTable(t))
            trans.commit()


class RedisIsolation(object):

    @classmethod
    def setup_redis(cls):
        cls.redis_client = _make_redis()

    @classmethod
    def teardown_redis(cls):
        cls.redis_client.connection_pool.disconnect()
        del cls.redis_client

    @classmethod
    def cleanup_redis(cls):
        cls.redis_client.flushdb()


class CeleryIsolation(object):

    @classmethod
    def setup_celery(cls):
        cls.celery_app = celery_app
        init_worker(
            celery_app, TEST_CONFIG,
            _db_rw=cls.db_rw,
            _raven_client=cls.raven_client,
            _redis_client=cls.redis_client,
            _stats_client=cls.stats_client)

    @classmethod
    def teardown_celery(cls):
        del cls.celery_app.db_rw
        del cls.celery_app.raven_client
        del cls.celery_app.redis_client
        del cls.celery_app.stats_client
        del cls.celery_app.all_queues
        del cls.celery_app.data_queues
        del cls.celery_app.export_queues
        del cls.celery_app.settings
        del cls.celery_app


class LogIsolation(object):

    @classmethod
    def setup_logging(cls):
        # Use a debug configuration
        cls.raven_client = configure_raven('', DebugRavenClient())
        cls.stats_client = configure_stats('', DebugStatsClient())

    @classmethod
    def teardown_logging(cls):
        del cls.raven_client
        del cls.stats_client

    def clear_log_messages(self):
        self.raven_client._clear()
        self.stats_client._clear()

    def find_stats_messages(self, msg_type, msg_name, msg_value=None):
        data = {
            'counter': [],
            'timer': [],
            'gauge': [],
            'histogram': [],
            'meter': [],
            'set': [],
        }
        for m in self.stats_client.msgs:
            suffix = m.split('|')[-1]
            name, value = m.split('|')[0].split(':')
            value = int(value)
            if suffix == 'g':
                data['gauge'].append((name, value))
            elif suffix == 'ms':
                data['timer'].append((name, value))
            elif suffix.startswith('c'):
                data['counter'].append((name, value))
            elif suffix == 'h':
                data['histogram'].append((name, value))
            elif suffix == 'm':
                data['meter'].append((name, value))
            elif suffix == 's':
                data['set'].append((name, value))

        result = []
        for m in data.get(msg_type):
            if m[0] == msg_name:
                if msg_value is None or m[1] == msg_value:
                    result.append((m[0], m[1]))
        return result

    def check_raven(self, expected=None, total=None):
        """Checks the raven message stream looking for the expected messages.

        The expected argument should be a list of either names or tuples.

        If it is a tuple, it should be a tuple of name and an expected count.

        The names are matched via startswith against the captured exception
        messages.
        """
        msgs = self.raven_client.msgs
        found_msgs = [msg['message'] for msg in msgs]
        if expected is None:
            expected = ()
        if total is not None:
            self.assertEqual(len(msgs), total, found_msgs)
        for exp in expected:
            count = 1
            name = exp
            if isinstance(exp, tuple):
                name, count = exp
            matches = [found for found in found_msgs if found.startswith(name)]
            self.assertEqual(len(matches), count, found_msgs)

    def check_stats(self, total=None, **kw):
        """Checks a partial specification of messages to be found in
        the stats message stream.

        Keyword arguments:
        total --  (optional) exact count of messages expected in stream.
        kw  --  for all remaining keyword args of the form k:v :

            select messages of type k, comparing the
            message fields against v subject to type-dependent
            interpretation:

              if v is a str, select messages with name == v
              and let match = 1

              if v is a 2-tuple (n, match), select messages with
              name == n

              if v is a 3-tuple (n, match, value), select messages with
              name == n and value == value

           the selected messages are then checked depending on the type
           of match:

              if match is an int, assert match messages were selected

        Examples:

           check_stats(
               total=4,
               timer=['request.v1.search'],
               counter=['search.api_key.test',
                        ('items.uploaded.batches', 2)],
           )

           This call will check for exactly 4 messages, exactly one timer
           with 'name':'request.v1.search', exactly one counter
           with 'name':'search.api_key.test'and  exactly two counters with
           'name':'items.uploaded.batches'.
        """
        if total is not None:
            self.assertEqual(total, len(self.stats_client.msgs),
                             self.stats_client.msgs)

        for (msg_type, pred) in kw.items():
            for p in pred:
                match = 1
                value = None
                if isinstance(p, str):
                    name = p
                elif isinstance(p, tuple):
                    if len(p) == 2:
                        (name, match) = p
                    elif len(p) == 3:
                        (name, match, value) = p
                    else:
                        raise TypeError("wanted 2 or 3-element tuple, got %s"
                                        % type(p))
                else:
                    raise TypeError("wanted str or tuple, got %s"
                                    % type(p))
                msgs = self.find_stats_messages(msg_type, name, value)
                if isinstance(match, int):
                    self.assertEqual(match, len(msgs),
                                     msg='%s %s not found' % (msg_type, name))


class GeoIPIsolation(object):

    geoip_data = GEOIP_DATA

    @classmethod
    def configure_geoip(cls, filename=None, mode=MODE_AUTO, raven_client=None):
        if filename is None:
            filename = GEOIP_TEST_FILE
        return configure_geoip(filename=filename, mode=mode,
                               raven_client=raven_client)

    @classmethod
    def setup_geoip(cls, raven_client=None):
        cls.geoip_db = cls.configure_geoip(raven_client=raven_client)

    @classmethod
    def teardown_geoip(cls):
        del cls.geoip_db


class AppTestCase(TestCase, DBIsolation,
                  RedisIsolation, LogIsolation, GeoIPIsolation):

    default_session = 'db_ro_session'

    @classmethod
    def setUpClass(cls):
        super(AppTestCase, cls).setup_engine()
        super(AppTestCase, cls).setup_redis()
        super(AppTestCase, cls).setup_logging()
        super(AppTestCase, cls).setup_geoip()

        cls.app = _make_app(app_config=TEST_CONFIG,
                            _db_rw=cls.db_rw,
                            _db_ro=cls.db_ro,
                            _geoip_db=cls.geoip_db,
                            _raven_client=cls.raven_client,
                            _redis_client=cls.redis_client,
                            _stats_client=cls.stats_client,
                            )

    @classmethod
    def tearDownClass(cls):
        del cls.app
        super(AppTestCase, cls).teardown_engine()
        super(AppTestCase, cls).teardown_redis()
        super(AppTestCase, cls).teardown_logging()
        super(AppTestCase, cls).teardown_geoip()

    def setUp(self):
        self.setup_session()
        self.clear_log_messages()

    def tearDown(self):
        self.cleanup_redis()
        self.teardown_session()


class DBTestCase(TestCase, DBIsolation, LogIsolation):

    @classmethod
    def setUpClass(cls):
        super(DBTestCase, cls).setup_engine()
        super(DBTestCase, cls).setup_logging()

    @classmethod
    def tearDownClass(cls):
        super(DBTestCase, cls).teardown_engine()
        super(DBTestCase, cls).teardown_logging()

    def setUp(self):
        self.setup_session()
        self.clear_log_messages()

    def tearDown(self):
        self.teardown_session()


class CeleryTestCase(DBTestCase, RedisIsolation, CeleryIsolation):

    @classmethod
    def setUpClass(cls):
        super(CeleryTestCase, cls).setUpClass()
        super(CeleryTestCase, cls).setup_redis()
        super(CeleryTestCase, cls).setup_celery()

    @classmethod
    def tearDownClass(cls):
        super(CeleryTestCase, cls).teardown_celery()
        super(CeleryTestCase, cls).teardown_redis()
        super(CeleryTestCase, cls).tearDownClass()

    def tearDown(self):
        self.cleanup_redis()
        self.teardown_session()


class CeleryAppTestCase(AppTestCase, CeleryIsolation):

    default_session = 'db_rw_session'

    @classmethod
    def setUpClass(cls):
        super(CeleryAppTestCase, cls).setUpClass()
        super(CeleryAppTestCase, cls).setup_celery()

    @classmethod
    def tearDownClass(cls):
        super(CeleryAppTestCase, cls).teardown_celery()
        super(CeleryAppTestCase, cls).tearDownClass()


def setup_package(module):
    # make sure all models are imported
    from ichnaea.models import base  # NOQA
    from ichnaea.models import content  # NOQA
    db = _make_db()
    engine = db.engine
    DBIsolation.cleanup_tables(engine)
    DBIsolation.setup_tables(engine)
    # always add a test API key
    session = db.session()
    session.add(ApiKey(valid_key='test', log=True, shortname='test'))
    session.add(ApiKey(valid_key='export', log=False, shortname='export'))
    session.commit()
    session.close()
    db.engine.pool.dispose()


def teardown_package(module):
    pass
