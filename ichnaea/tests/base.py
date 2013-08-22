import os

from unittest2 import TestCase
from webtest import TestApp

from ichnaea import main
from ichnaea.db import _Model
from ichnaea.db import Database
from ichnaea.worker import attach_database
from ichnaea.worker import celery

SQLURI = os.environ.get('SQLURI')
SQLSOCKET = os.environ.get('SQLSOCKET')


def _make_db(create=True):
    return Database(SQLURI, socket=SQLSOCKET, create=create)


def _make_app(_db_master=None, _db_slave=None, **settings):
    wsgiapp = main({}, _db_master=_db_master, _db_slave=_db_slave, **settings)
    return TestApp(wsgiapp)


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
        self.master_trans.rollback()
        self.db_master_session.close()

    def cleanup(self, engine):
        with engine.connect() as conn:
            trans = conn.begin()
            _Model.metadata.drop_all(engine)
            trans.commit()


class AppTestCase(TestCase, DBIsolation):

    @classmethod
    def setUpClass(cls):
        cls.db_master = _make_db()
        cls.db_slave = _make_db(create=False)
        cls.app = _make_app(_db_master=cls.db_master, _db_slave=cls.db_slave)

    def setUp(self):
        self.setup_session()

    def tearDown(self):
        self.teardown_session()


class DBTestCase(TestCase, DBIsolation):

    @classmethod
    def setUpClass(cls):
        cls.db_master = _make_db()
        cls.db_slave = _make_db(create=False)

    def setUp(self):
        self.setup_session()

    def tearDown(self):
        self.teardown_session()


class CeleryTestCase(DBTestCase):

    @classmethod
    def setUpClass(cls):
        super(CeleryTestCase, cls).setUpClass()
        cls._old_db = getattr(celery, 'db_master', None)
        attach_database(celery, cls.db_master)

    @classmethod
    def tearDownClass(cls):
        if cls._old_db is not None:
            setattr(celery, 'db_master', cls._old_db)
        else:
            delattr(celery, 'db_master')
        super(CeleryTestCase, cls).tearDownClass()
