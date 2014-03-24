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
    return Database(uri, socket=socket, create=create, model_class=_Model)


def _make_app(_archival_db=None, _volatile_db=None, **settings):
    wsgiapp = main({}, _archival_db=_archival_db, _volatile_db=_volatile_db, **settings)
    return TestApp(wsgiapp)


def find_msg(msgs, msg_type, field_value, field_name='name'):
    return [m for m in msgs if m.type == msg_type and
           [f for f in m.fields if f.name == field_name and
            f.value_string == [field_value]]]


class DBIsolation(object):
    # Inspired by a blog post:
    # http://sontek.net/blog/detail/writing-tests-for-pyramid-and-sqlalchemy

    def setup_session(self):
        archival_conn = self.archival_db.engine.connect()
        self.archival_trans = archival_conn.begin()
        self.archival_db.session_factory.configure(bind=archival_conn)
        self.archival_db_session = self.archival_db.session()
        volatile_conn = self.volatile_db.engine.connect()
        self.volatile_trans = volatile_conn.begin()
        self.volatile_db.session_factory.configure(bind=volatile_conn)
        self.volatile_db_session = self.volatile_db.session()

    def teardown_session(self):
        self.volatile_trans.rollback()
        self.volatile_db_session.close()
        del self.volatile_db_session
        self.volatile_trans.close()
        self.volatile_db.session_factory.configure(bind=None)
        del self.volatile_trans
        self.archival_trans.rollback()
        self.archival_db_session.close()
        del self.archival_db_session
        self.archival_trans.close()
        self.archival_db.session_factory.configure(bind=None)
        del self.archival_trans

    @classmethod
    def setup_engine(cls):
        cls.archival_db = _make_db()
        cls.volatile_db = _make_db(create=False)

    @classmethod
    def teardown_engine(cls):
        cls.archival_db.engine.pool.dispose()
        del cls.archival_db
        cls.volatile_db.engine.pool.dispose()
        del cls.volatile_db

    def cleanup(self, engine):
        with engine.connect() as conn:
            trans = conn.begin()
            _Model.metadata.drop_all(engine)
            trans.commit()


class CeleryIsolation(object):

    @classmethod
    def attach_database(cls):
        attach_database(celery, cls.archival_db)

    @classmethod
    def detach_database(cls):
        del celery.archival_db


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

        cls.app = _make_app(_archival_db=cls.archival_db,
                            _volatile_db=cls.volatile_db,
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
