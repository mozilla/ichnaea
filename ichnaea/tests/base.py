import os

from unittest2 import TestCase
from webtest import TestApp

from ichnaea import main
from ichnaea.db import _Model
from ichnaea.db import Database

SQLURI = os.environ['SQLURI']
SQLSOCKET = os.environ['SQLSOCKET']


def _make_db(create=True, echo=False):
    return Database(SQLURI, socket=SQLSOCKET, create=create, echo=echo)


def _make_app():
    settings = {
        'db_master': SQLURI,
        'db_master_socket': SQLSOCKET,
        'db_slave': SQLURI,
        'db_slave_socket': SQLSOCKET,
    }
    wsgiapp = main({}, **settings)
    return TestApp(wsgiapp)


class DBIsolation(object):
    # Inspired by a blog post:
    # http://sontek.net/blog/detail/writing-tests-for-pyramid-and-sqlalchemy

    def setup_session(self):
        conn = self.db_master.engine.connect()
        self.trans = conn.begin()
        self.db_master.session_factory.configure(bind=conn)
        self.db_session = self.db_master.session()

    def teardown_session(self):
        self.trans.rollback()
        self.db_session.close()
        del self.trans
        del self.db_session

    def cleanup(self, engine):
        with engine.connect() as conn:
            trans = conn.begin()
            _Model.metadata.drop_all(engine)
            trans.commit()


class AppTestCase(TestCase, DBIsolation):

    def setUp(self):
        self.app = _make_app()
        self.db_master = self.app.app.registry.db_master
        self.db_slave = self.app.app.registry.db_slave
        self.setup_session()

    def tearDown(self):
        self.teardown_session()
        del self.db_slave
        del self.db_master
        del self.app


class DBTestCase(TestCase, DBIsolation):

    def setUp(self):
        self.db_master = _make_db()
        self.setup_session()

    def tearDown(self):
        self.teardown_session()
        del self.db_master
