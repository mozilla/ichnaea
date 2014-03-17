import os
import os.path

from heka.encoders import NullEncoder
from heka.streams import DebugCaptureStream
from unittest2 import TestCase
from webtest import TestApp

from ichnaea import main
from ichnaea.db import _Model
from ichnaea.db import Database
from ichnaea.geoip import configure_geoip
from ichnaea.heka_logging import configure_heka
from ichnaea.worker import attach_database
from ichnaea.worker import celery

# make new unittest API's available under Python 2.6
try:
    from unittest2 import TestCase  # NOQA
except ImportError:
    from unittest import TestCase


SQLURI = os.environ.get('SQLURI')
SQLSOCKET = os.environ.get('SQLSOCKET')


def _make_db(uri=SQLURI, socket=SQLSOCKET, create=True):
    return Database(uri, socket=socket, create=create)


def _make_app(_db_master=None, _db_slave=None, **settings):
    wsgiapp = main({}, _db_master=_db_master, _db_slave=_db_slave, **settings)
    return TestApp(wsgiapp)


def find_msg(msgs, msg_type, field_value, field_name='name'):
    return [m for m in msgs if m.type == msg_type and
           [f for f in m.fields if f.name == field_name and
            f.value_string == [field_value]]]


class DBIsolation(object):
    # Inspired by a blog post:
    # http://sontek.net/blog/detail/writing-tests-for-pyramid-and-sqlalchemy

    def setup_session(self):
        master_conn = self.db_master.engine.connect()
        self.master_trans = master_conn.begin()
        self.db_master.session_factory.configure(bind=master_conn)
        self.db_master_session = self.db_master.session()
        slave_conn = self.db_slave.engine.connect()
        self.slave_trans = slave_conn.begin()
        self.db_slave.session_factory.configure(bind=slave_conn)
        self.db_slave_session = self.db_slave.session()

    def teardown_session(self):
        self.slave_trans.rollback()
        self.db_slave_session.close()
        del self.db_slave_session
        self.slave_trans.close()
        self.db_slave.session_factory.configure(bind=None)
        del self.slave_trans
        self.master_trans.rollback()
        self.db_master_session.close()
        del self.db_master_session
        self.master_trans.close()
        self.db_master.session_factory.configure(bind=None)
        del self.master_trans

    @classmethod
    def setup_engine(cls):
        cls.db_master = _make_db()
        cls.db_slave = _make_db(create=False)

    @classmethod
    def teardown_engine(cls):
        cls.db_master.engine.pool.dispose()
        del cls.db_master
        cls.db_slave.engine.pool.dispose()
        del cls.db_slave

    def cleanup(self, engine):
        with engine.connect() as conn:
            trans = conn.begin()
            _Model.metadata.drop_all(engine)
            trans.commit()


class CeleryIsolation(object):

    @classmethod
    def attach_database(cls):
        attach_database(celery, cls.db_master)

    @classmethod
    def detach_database(cls):
        del celery.db_master


class HekaIsolation(object):

    @classmethod
    def setup_heka(cls):
        # Clobber the stream with a debug version
        cls.heka_client = configure_heka()
        cls.heka_client.stream = DebugCaptureStream()
        cls.heka_client.encoder = NullEncoder(None)

    @classmethod
    def teardown_heka(cls):
        del cls.heka_client

    def clear_heka_messages(self):
        self.heka_client.stream.msgs.clear()

    def find_heka_messages(self, *args, **kw):
        msgs = self.heka_client.stream.msgs
        return find_msg(msgs, *args, **kw)


class GeoIPIsolation(object):

    @classmethod
    def setup_geoip(cls):
        filename = os.path.join(os.path.dirname(__file__), 'GeoIPCity.dat')
        cls.geoip_db = configure_geoip(filename=filename)

    @classmethod
    def teardown_geoip(cls):
        del cls.geoip_db


class AppTestCase(TestCase, DBIsolation, HekaIsolation, GeoIPIsolation):

    @classmethod
    def setUpClass(cls):
        super(AppTestCase, cls).setup_engine()
        super(AppTestCase, cls).setup_heka()
        super(AppTestCase, cls).setup_geoip()

        cls.app = _make_app(_db_master=cls.db_master,
                            _db_slave=cls.db_slave,
                            _heka_client=cls.heka_client,
                            _geoip_db=cls.geoip_db)

    @classmethod
    def tearDownClass(cls):
        del cls.app
        super(AppTestCase, cls).teardown_engine()
        super(AppTestCase, cls).teardown_heka()
        super(AppTestCase, cls).teardown_geoip()

    def setUp(self):
        self.setup_session()
        self.clear_heka_messages()

    def tearDown(self):
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
        super(CeleryTestCase, cls).attach_database()

    @classmethod
    def tearDownClass(cls):
        super(CeleryTestCase, cls).detach_database()
        super(CeleryTestCase, cls).tearDownClass()


class CeleryAppTestCase(AppTestCase, CeleryIsolation):

    @classmethod
    def setUpClass(cls):
        super(CeleryAppTestCase, cls).setUpClass()
        super(CeleryAppTestCase, cls).attach_database()

    @classmethod
    def tearDownClass(cls):
        super(CeleryAppTestCase, cls).detach_database()
        super(CeleryAppTestCase, cls).tearDownClass()
