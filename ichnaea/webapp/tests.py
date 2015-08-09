from ichnaea.config import DummyConfig
from ichnaea.geoip import GeoIPNull
from ichnaea.tests.base import (
    _make_app,
    _make_db,
    _make_redis,
    AppTestCase,
    ConnectionTestCase,
    REDIS_URI,
    SQLURI,
)


class TestApp(ConnectionTestCase):

    def test_db_config(self):
        app_config = DummyConfig({
            'database': {
                'rw_url': SQLURI,
                'ro_url': SQLURI,
            },
        })
        app = _make_app(app_config=app_config,
                        _raven_client=self.raven_client,
                        _redis_client=self.redis_client,
                        _stats_client=self.stats_client,
                        )
        db_rw = app.app.registry.db_rw
        db_ro = app.app.registry.db_ro
        # the configured databases are working
        try:
            self.assertTrue(db_rw.ping())
            self.assertTrue(db_ro.ping())
        finally:
            # clean up the new db engine's _make_app created
            db_rw.engine.pool.dispose()
            db_ro.engine.pool.dispose()

    def test_db_hooks(self):
        db_rw = _make_db()
        db_ro = _make_db()
        app = _make_app(_db_rw=db_rw,
                        _db_ro=db_ro,
                        _raven_client=self.raven_client,
                        _redis_client=self.redis_client,
                        _stats_client=self.stats_client,
                        )
        # check that our _db hooks are passed through
        self.assertTrue(app.app.registry.db_rw is db_rw)
        self.assertTrue(app.app.registry.db_ro is db_ro)

    def test_redis_config(self):
        app_config = DummyConfig({
            'cache': {
                'cache_url': REDIS_URI,
            },
        })
        app = _make_app(app_config=app_config,
                        _db_rw=self.db_rw,
                        _db_ro=self.db_ro,
                        _raven_client=self.raven_client,
                        _stats_client=self.stats_client)
        redis_client = app.app.registry.redis_client
        self.assertTrue(redis_client is not None)
        self.assertEqual(
            redis_client.connection_pool.connection_kwargs['db'], 1)


class TestHeartbeat(AppTestCase):

    def test_ok(self):
        app = self.app
        res = app.get('/__heartbeat__', status=200)
        self.assertEqual(res.content_type, 'application/json')
        self.assertEqual(res.json['status'], 'OK')


class TestDatabaseHeartbeat(AppTestCase):

    def test_database_error(self):
        # self.app is a class variable, so we keep this test in
        # its own class to avoid isolation problems
        app = self.app

        # create a database connection to the discard port
        self.app.app.registry.db_ro = _make_db(
            uri='mysql+pymysql://none:none@127.0.0.1:9/test_location')

        res = app.get('/__heartbeat__', status=200)
        self.assertEqual(res.content_type, 'application/json')
        self.assertEqual(res.json['status'], 'OK')


class TestMonitor(AppTestCase):

    def test_ok(self):
        app = self.app
        response = app.get('/__monitor__', status=200)
        self.assertEqual(response.content_type, 'application/json')
        data = response.json
        timed_services = set(['database', 'geoip', 'redis'])
        self.assertEqual(set(data.keys()), timed_services)

        for name in timed_services:
            self.assertEqual(data[name]['up'], True)
            self.assertTrue(isinstance(data[name]['time'], int))
            self.assertTrue(data[name]['time'] >= 0)

        self.assertTrue(1 < data['geoip']['age_in_days'] < 1000)


class TestMonitorErrors(AppTestCase):

    def setUp(self):
        super(TestMonitorErrors, self).setUp()
        # create database connections to the discard port
        db_uri = 'mysql+pymysql://none:none@127.0.0.1:9/none'
        self.broken_db = _make_db(uri=db_uri)
        self.app.app.registry.db_rw = self.broken_db
        self.app.app.registry.db_ro = self.broken_db
        # create broken geoip db
        self.app.app.registry.geoip_db = GeoIPNull()
        # create broken redis connection
        redis_uri = 'redis://127.0.0.1:9/15'
        self.broken_redis = _make_redis(redis_uri)
        self.app.app.registry.redis_client = self.broken_redis

    def tearDown(self):
        super(TestMonitorErrors, self).tearDown()
        del self.broken_db
        self.broken_redis.connection_pool.disconnect()
        del self.broken_redis

    def test_database_error(self):
        res = self.app.get('/__monitor__', status=503)
        self.assertEqual(res.content_type, 'application/json')
        self.assertEqual(res.json['database'], {'up': False, 'time': 0})

    def test_geoip_error(self):
        res = self.app.get('/__monitor__', status=503)
        self.assertEqual(res.content_type, 'application/json')
        self.assertEqual(res.json['geoip'],
                         {'up': False, 'time': 0, 'age_in_days': -1})

    def test_redis_error(self):
        res = self.app.get('/__monitor__', status=503)
        self.assertEqual(res.content_type, 'application/json')
        self.assertEqual(res.json['redis'], {'up': False, 'time': 0})


class TestVersion(AppTestCase):

    def test_ok(self):
        app = self.app
        response = app.get('/__version__', status=200)
        self.assertEqual(response.content_type, 'application/json')
        data = response.json
        self.assertEqual(
            set(data.keys()), set(['commit', 'source', 'tag', 'version']))
        self.assertEqual(data['source'], 'https://github.com/mozilla/ichnaea')
