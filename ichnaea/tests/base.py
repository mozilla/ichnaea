import os

from unittest2 import TestCase
from webtest import TestApp

from ichnaea import main
from ichnaea.db import _Model
from ichnaea.db import Database
from ichnaea.worker import attach_database
from ichnaea.worker import celery

from heka.streams import DebugCaptureStream
from heka.encoders import NullEncoder

SQLURI = os.environ.get('SQLURI')
SQLSOCKET = os.environ.get('SQLSOCKET')


def _make_db(create=True):
    return Database(SQLURI, socket=SQLSOCKET, create=create)


def _make_app(_db_master=None, _db_slave=None, **settings):
    wsgiapp = main({}, _db_master=_db_master, _db_slave=_db_slave, **settings)
    return TestApp(wsgiapp)

def find_msg(msgs, msg_type, field_name):
    shortlist = [m for m in msgs if m.type == msg_type and
                [f for f in m.fields if f.name == 'name' and
                 f.value_string == [field_name]]]
    return shortlist


def use_hekatest(heka_client):
    heka_client.stream = DebugCaptureStream()
    heka_client.encoder = NullEncoder(None)

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


class AppTestCase(TestCase, DBIsolation):

    @classmethod
    def setUpClass(cls):
        super(AppTestCase, cls).setup_engine()

        # Clobber the stream with a debug version
        from heka.holder import get_client
        from ichnaea.heka_logging import configure_heka
        heka_client = configure_heka()
        use_hekatest(heka_client)

        cls.app = _make_app(_db_master=cls.db_master,
                            _db_slave=cls.db_slave,
                            _heka_client=heka_client)

    @classmethod
    def tearDownClass(cls):
        del cls.app
        super(AppTestCase, cls).teardown_engine()

    def setUp(self):
        self.setup_session()

    def tearDown(self):
        self.teardown_session()


class DBTestCase(TestCase, DBIsolation):

    @classmethod
    def setUpClass(cls):
        super(DBTestCase, cls).setup_engine()

        # Clobber the stream with a debug version
        from heka.holder import get_client
        heka_client = get_client('ichnaea')
        use_hekatest(heka_client)

    @classmethod
    def tearDownClass(cls):
        super(DBTestCase, cls).teardown_engine()

    def setUp(self):
        self.setup_session()

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
