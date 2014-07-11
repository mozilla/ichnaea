import os
import os.path

from alembic.config import Config
from alembic import command
from sqlalchemy import inspect
from sqlalchemy.schema import (
    DropTable,
    MetaData,
    Table,
)
from unittest2 import TestCase
from webtest import TestApp

from ichnaea import main
from ichnaea.cache import redis_client
from ichnaea.db import _Model
from ichnaea.db import Database
from ichnaea.geoip import configure_geoip
from ichnaea.heka_logging import configure_heka
from ichnaea.models import ApiKey
from ichnaea.stats import (
    configure_stats,
    DebugStatsClient,
)
from ichnaea.worker import (
    attach_database,
    celery,
    configure_s3_backup,
)

# make new unittest API's available under Python 2.6
try:
    from unittest2 import TestCase  # NOQA
except ImportError:
    from unittest import TestCase

TEST_DIRECTORY = os.path.dirname(__file__)
HEKA_TEST_CONFIG = os.path.join(TEST_DIRECTORY, 'heka.ini')

SQLURI = os.environ.get('SQLURI')
REDIS_URI = os.environ.get('REDIS_URI', 'redis://localhost:6379/1')

# Some test-data constants

USA_MCC = 310
ATT_MNC = 150

FREMONT_IP = '66.92.181.240'
FREMONT_LAT = 37.5079
FREMONT_LON = -121.96

BRAZIL_MCC = 724
VIVO_MNC = 11

SAO_PAULO_IP = '200.153.101.58'
SAO_PAULO_LAT = -23.54
SAO_PAULO_LON = -46.64

PORTO_ALEGRE_LAT = -30.032
PORTO_ALEGRE_LON = -51.22

FRANCE_MCC = 208
VIVENDI_MNC = 10

PARIS_IP = '146.0.66.11'
PARIS_LAT = 48.8568
PARIS_LON = 2.3508


def _make_db(uri=SQLURI):
    return Database(uri)


def _make_redis(uri=REDIS_URI):
    return redis_client(uri)


def _make_app(_db_master=None, _db_slave=None, _heka_client=None, _redis=None,
              _stats_client=None, **settings):
    wsgiapp = main(
        {},
        _db_master=_db_master,
        _db_slave=_db_slave,
        _heka_client=_heka_client,
        _redis=_redis,
        _stats_client=_stats_client,
        **settings)
    return TestApp(wsgiapp)


def find_msg(msgs, msg_type, field_value, field_name='name'):
    return [m for m in msgs if m.type == msg_type and
            [f for f in m.fields if f.name == field_name and
             f.value_string == [field_value]]]


class DBIsolation(object):
    # Inspired by a blog post:
    # http://sontek.net/blog/detail/writing-tests-for-pyramid-and-sqlalchemy

    def setup_session(self):
        self.master_conn = self.db_master.engine.connect()
        self.master_trans = self.master_conn.begin()
        self.db_master.session_factory.configure(bind=self.master_conn)
        self.db_master_session = self.db_master.session()
        self.slave_conn = self.db_slave.engine.connect()
        self.slave_trans = self.slave_conn.begin()
        self.db_slave.session_factory.configure(bind=self.slave_conn)
        self.db_slave_session = self.db_slave.session()

    def teardown_session(self):
        self.slave_trans.rollback()
        self.db_slave_session.close()
        del self.db_slave_session
        self.db_slave.session_factory.configure(bind=None)
        self.slave_trans.close()
        del self.slave_trans
        self.slave_conn.close()
        del self.slave_conn
        self.master_trans.rollback()
        self.db_master_session.close()
        del self.db_master_session
        self.db_master.session_factory.configure(bind=None)
        self.master_trans.close()
        del self.master_trans
        self.master_conn.close()
        del self.master_conn

    @classmethod
    def setup_engine(cls):
        cls.db_master = _make_db()
        cls.db_slave = _make_db()

    @classmethod
    def teardown_engine(cls):
        cls.db_master.engine.pool.dispose()
        del cls.db_master
        cls.db_slave.engine.pool.dispose()
        del cls.db_slave

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
        attach_database(celery, _db_master=cls.db_master)
        configure_s3_backup(celery, settings={
            's3_backup_bucket': 'localhost.bucket',
        })

    @classmethod
    def teardown_celery(cls):
        del celery.s3_settings
        del celery.db_master


class HekaIsolation(object):

    @classmethod
    def setup_heka(cls):
        # Use a debug configuration
        cls.heka_client = configure_heka(HEKA_TEST_CONFIG)
        cls.stats_client = configure_stats('', DebugStatsClient())

    @classmethod
    def teardown_heka(cls):
        del cls.heka_client
        del cls.stats_client

    def clear_heka_messages(self):
        self.heka_client.stream.msgs.clear()
        self.stats_client.msgs.clear()

    def find_heka_messages(self, *args, **kw):
        msgs = self.heka_client.stream.msgs
        return find_msg(msgs, *args, **kw)

    def print_heka_messages(self):
        i = 0
        for m in self.heka_client.stream.msgs:
            print("Heka Message #%d:" % i)
            i += 1
            for field in m.fields:
                print("    field: %s = %s" %
                      (field.name, ", ".join(field.value_string)))

    def find_stats_messages(self, msg_type, msg_name):
        result = {
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
            if suffix == 'g':
                result['gauge'].append((name, value))
            elif suffix == 'ms':
                result['timer'].append((name, value))
            elif suffix.startswith('c'):
                result['counter'].append((name, value))
            elif suffix == 'h':
                result['histogram'].append((name, value))
            elif suffix == 'm':
                result['meter'].append((name, value))
            elif suffix == 's':
                result['set'].append((name, value))
        return [(m[0], m[1]) for m in result.get(msg_type)
                if m[0].startswith(msg_name)]

    def print_stats_messages(self):
        for m in self.stats_client.msgs:
            print(m)

    def check_stats(self, total=None, **kw):
        """Checks a partial specification of messages to be found in
        the stats message stream.

        Keyword arguments:
        total --  (optional) exact count of messages expected in stream.
        kw  --  for all remaining keyword args of the form k:v :

            select messages of type k, comparing the
            message fields against v subject to type-dependent
            interpretation:

              if v is a str, select messages with field 'name' == v
              and let match = 1

              if v is a 2-tuple (n, match), select messages with
              field 'name' == n

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
            self.assertEqual(total, len(self.stats_client.msgs))

        for (msg_type, pred) in kw.items():
            for p in pred:
                match = 1
                if isinstance(p, str):
                    name = p
                elif isinstance(p, tuple):
                    if len(p) == 2:
                        (name, match) = p
                    else:
                        raise TypeError("wanted 2-element tuple, got %s"
                                        % type(p))
                else:
                    raise TypeError("wanted str or tuple, got %s"
                                    % type(p))
                msgs = self.find_stats_messages(msg_type, name)
                if isinstance(match, int):
                    self.assertEqual(match, len(msgs))
                else:
                    raise TypeError("wanted int, got %s" % type(match))

    def check_expected_heka_messages(self, total=None, **kw):
        """Checks a partial specification of messages to be found in
        the heka message stream.

        Keyword arguments:
        total --  (optional) exact count of messages expected in stream.
        kw  --  for all remaining keyword args of the form k:v :

                select messages of heka message-type k, comparing the
                message fields against v subject to type-dependent
                interpretation:

                  if v is a str, select messages with field 'name' == v
                  and let match = 1

                  if v is a 2-tuple (n, match), select messages with
                  field 'name' == n

                  if v is a 3-tuple, (f, n, match), select messages
                  with field f == n

               the selected messages are then checked depending on the type
               of match:

                  if match is an int, assert match messages were selected

                  if match is a dict, assert that at least one message
                  exists with each f:n entry in the mapping in the message
                  field list.

        Examples:

           check_expected_heka_messages(timer=['request'])

           This call will check for exactly one timer message with
           'name':'request' in its fields.


           check_expected_heka_messages(
               total=5,
               timer=[('request', {'url_path': '/v1/search'})],
               counter=['search.api_key.test',
                        ('items.uploaded.batches', 2)],
               sentry=[('msg', RAVEN_ERROR, 1)]
           )

           This call will check for exactly 5 messages, exactly one timer
           with 'name':'request' and 'url_path':'/v1/search' in its
           fields; exactly one counter with 'name':'search.api_key.test',
           exactly two counters with 'name':'items.uploaded.batches', and
           at least one sentry message with 'msg':RAVEN_ERROR in its
           fields.

        """

        if total is not None:
            self.assertEqual(total, len(self.heka_client.stream.msgs))

        for (msg_type, pred) in kw.items():
            for p in pred:
                fname = 'name'
                match = 1
                if isinstance(p, str):
                    name = p
                elif isinstance(p, tuple):
                    if len(p) == 2:
                        (name, match) = p
                    elif len(p) == 3:
                        (fname, name, match) = p
                    else:
                        raise TypeError("wanted 2 or 3-element tuple, got %s"
                                        % type(p))
                else:
                    raise TypeError("wanted str or tuple, got %s"
                                    % type(p))
                msgs = self.find_heka_messages(msg_type, name,
                                               field_name=fname)
                if isinstance(match, int):
                    self.assertEqual(match, len(msgs))
                elif isinstance(match, dict):
                    matching = []
                    for msg in msgs:
                        for (k, v) in match.items():
                            for f in msg.fields:
                                if f.name == k and f.value_string == [v]:
                                    matching.append(msg)
                    self.assertNotEqual(matching, [])
                else:
                    raise TypeError("wanted int or dict, got %s" % type(match))


class GeoIPIsolation(object):

    @classmethod
    def setup_geoip(cls):
        filename = os.path.join(os.path.dirname(__file__), 'GeoIPCity.dat')
        cls.geoip_db = configure_geoip(filename=filename)

    @classmethod
    def teardown_geoip(cls):
        del cls.geoip_db


class AppTestCase(TestCase, DBIsolation,
                  RedisIsolation, HekaIsolation, GeoIPIsolation):

    @classmethod
    def setUpClass(cls):
        super(AppTestCase, cls).setup_engine()
        super(AppTestCase, cls).setup_redis()
        super(AppTestCase, cls).setup_heka()
        super(AppTestCase, cls).setup_geoip()

        cls.app = _make_app(_db_master=cls.db_master,
                            _db_slave=cls.db_slave,
                            _heka_client=cls.heka_client,
                            _redis=cls.redis_client,
                            _stats_client=cls.stats_client,
                            _geoip_db=cls.geoip_db)

    @classmethod
    def tearDownClass(cls):
        del cls.app
        super(AppTestCase, cls).teardown_engine()
        super(AppTestCase, cls).teardown_redis()
        super(AppTestCase, cls).teardown_heka()
        super(AppTestCase, cls).teardown_geoip()

    def setUp(self):
        self.setup_session()
        self.clear_heka_messages()

    def tearDown(self):
        self.cleanup_redis()
        self.teardown_session()


class DBTestCase(TestCase, DBIsolation, HekaIsolation):

    @classmethod
    def setUpClass(cls):
        super(DBTestCase, cls).setup_engine()
        super(DBTestCase, cls).setup_heka()

    @classmethod
    def tearDownClass(cls):
        super(DBTestCase, cls).teardown_engine()
        super(DBTestCase, cls).teardown_heka()

    def setUp(self):
        self.setup_session()
        self.clear_heka_messages()

    def tearDown(self):
        self.teardown_session()


class CeleryTestCase(DBTestCase, CeleryIsolation):

    @classmethod
    def setUpClass(cls):
        super(CeleryTestCase, cls).setUpClass()
        super(CeleryTestCase, cls).setup_celery()

    @classmethod
    def tearDownClass(cls):
        super(CeleryTestCase, cls).teardown_celery()
        super(CeleryTestCase, cls).tearDownClass()


class CeleryAppTestCase(AppTestCase, CeleryIsolation):

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
    from ichnaea import models  # NOQA
    from ichnaea.content import models  # NOQA
    db = _make_db()
    engine = db.engine
    DBIsolation.cleanup_tables(engine)
    DBIsolation.setup_tables(engine)
    # always add a test API key
    session = db.session()
    session.add(ApiKey(valid_key='test', shortname='test'))
    session.commit()
    session.close()
    db.engine.pool.dispose()


def teardown_package(module):
    pass
