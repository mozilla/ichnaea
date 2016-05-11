import webtest

from ichnaea.cache import configure_redis
from ichnaea.config import DummyConfig
from ichnaea.geoip import GeoIPNull
from ichnaea.tests.base import (
    _make_db,
    AppTestCase,
    ConnectionTestCase,
    REDIS_URI,
    SQLURI,
    TEST_CONFIG,
)
from ichnaea.webapp.config import main


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
    return webtest.TestApp(wsgiapp)


class TestApp(ConnectionTestCase):

    def test_compiles(self):
        from ichnaea.webapp import app
        assert hasattr(app, 'wsgi_app')

    def test_db_config(self):
        app_config = DummyConfig({
            'database': {
                'rw_url': SQLURI,
                'ro_url': SQLURI,
            },
        })
        app = _make_app(app_config=app_config,
                        _geoip_db=self.geoip_db,
                        _raven_client=self.raven_client,
                        _redis_client=self.redis_client,
                        _stats_client=self.stats_client,
                        )
        db_rw = app.app.registry.db_rw
        db_ro = app.app.registry.db_ro
        # the configured databases are working
        try:
            assert db_rw.ping()
            assert db_ro.ping()
        finally:
            # clean up the new db engine's _make_app created
            db_rw.close()
            db_ro.close()

    def test_db_hooks(self):
        db_rw = _make_db()
        db_ro = _make_db()
        app = _make_app(_db_rw=db_rw,
                        _db_ro=db_ro,
                        _geoip_db=self.geoip_db,
                        _raven_client=self.raven_client,
                        _redis_client=self.redis_client,
                        _stats_client=self.stats_client,
                        )
        # check that our _db hooks are passed through
        assert app.app.registry.db_rw is db_rw
        assert app.app.registry.db_ro is db_ro
        db_rw.close()
        db_ro.close()

    def test_redis_config(self):
        app_config = DummyConfig({
            'cache': {
                'cache_url': REDIS_URI,
            },
        })
        app = _make_app(app_config=app_config,
                        _db_rw=self.db_rw,
                        _db_ro=self.db_ro,
                        _geoip_db=self.geoip_db,
                        _raven_client=self.raven_client,
                        _stats_client=self.stats_client)
        redis_client = app.app.registry.redis_client
        assert redis_client is not None
        assert redis_client.connection_pool.connection_kwargs['db'] == 1


class TestHeartbeat(AppTestCase):

    def test_ok(self):
        response = self.app.get('/__heartbeat__', status=200)
        assert response.content_type == 'application/json'
        data = response.json
        timed_services = set(['database', 'geoip', 'redis'])
        assert set(data.keys()) == timed_services

        for name in timed_services:
            assert data[name]['up']
            assert isinstance(data[name]['time'], int)
            assert data[name]['time'] >= 0

        assert 1 < data['geoip']['age_in_days'] < 1000


class TestHeartbeatErrors(AppTestCase):

    def setUp(self):
        super(TestHeartbeatErrors, self).setUp()
        # create database connections to the discard port
        db_uri = 'mysql+pymysql://none:none@127.0.0.1:9/none'
        self.broken_db = _make_db(uri=db_uri)
        self.app.app.registry.db_rw = self.broken_db
        self.app.app.registry.db_ro = self.broken_db
        # create broken geoip db
        self.app.app.registry.geoip_db = GeoIPNull()
        # create broken redis connection
        self.broken_redis = configure_redis('redis://127.0.0.1:9/15')
        self.app.app.registry.redis_client = self.broken_redis

    def tearDown(self):
        super(TestHeartbeatErrors, self).tearDown()
        self.broken_db.engine.pool.dispose()
        del self.broken_db
        self.broken_redis.close()
        del self.broken_redis

    def test_database_error(self):
        res = self.app.get('/__heartbeat__', status=503)
        assert res.content_type == 'application/json'
        assert res.json['database'] == {'up': False, 'time': 0}
        assert res.headers['Access-Control-Allow-Origin'] == '*'
        assert res.headers['Access-Control-Max-Age'] == '2592000'

    def test_geoip_error(self):
        res = self.app.get('/__heartbeat__', status=503)
        assert res.content_type == 'application/json'
        assert res.json['geoip'] == \
            {'up': False, 'time': 0, 'age_in_days': -1}

    def test_redis_error(self):
        res = self.app.get('/__heartbeat__', status=503)
        assert res.content_type == 'application/json'
        assert res.json['redis'] == {'up': False, 'time': 0}


class TestLBHeartbeat(AppTestCase):

    def test_get(self):
        res = self.app.get('/__lbheartbeat__', status=200)
        assert res.content_type == 'application/json'
        assert res.json['status'] == 'OK'
        assert res.headers['Access-Control-Allow-Origin'] == '*'
        assert res.headers['Access-Control-Max-Age'] == '2592000'

    def test_head(self):
        res = self.app.head('/__lbheartbeat__', status=200)
        assert res.content_type == 'application/json'
        assert res.body == b''

    def test_post(self):
        res = self.app.post('/__lbheartbeat__', status=200)
        assert res.content_type == 'application/json'
        assert res.json['status'] == 'OK'

    def test_options(self):
        res = self.app.options(
            '/__lbheartbeat__', status=200, headers={
                'Access-Control-Request-Method': 'POST',
                'Origin': 'localhost.local',
            })
        assert res.headers['Access-Control-Allow-Origin'] == '*'
        assert res.headers['Access-Control-Max-Age'] == '2592000'
        assert res.content_length is None
        assert res.content_type is None

    def test_unsupported_methods(self):
        self.app.delete('/__lbheartbeat__', status=405)
        self.app.patch('/__lbheartbeat__', status=405)
        self.app.put('/__lbheartbeat__', status=405)


class TestLBHeartbeatDatabase(AppTestCase):

    def test_database_error(self):
        # self.app is a class variable, so we keep this test in
        # its own class to avoid isolation problems

        # create a database connection to the discard port
        self.app.app.registry.db_ro = _make_db(
            uri='mysql+pymysql://none:none@127.0.0.1:9/test_location')

        res = self.app.get('/__lbheartbeat__', status=200)
        assert res.content_type == 'application/json'
        assert res.json['status'] == 'OK'


class TestSettings(object):

    def test_compiles(self):
        from ichnaea.webapp import settings
        assert type(settings.max_requests_jitter) == int


class TestVersion(AppTestCase):

    def test_ok(self):
        response = self.app.get('/__version__', status=200)
        assert response.content_type == 'application/json'
        data = response.json
        assert set(data.keys()) == set(['commit', 'source', 'tag', 'version'])
        assert data['source'] == 'https://github.com/mozilla/ichnaea'


class TestWorker(object):

    def test_compiles(self):
        from ichnaea.webapp import worker
        assert hasattr(worker, 'LocationGeventWorker')
