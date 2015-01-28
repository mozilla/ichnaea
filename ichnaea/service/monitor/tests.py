from ichnaea.geoip import GeoIPNull
from ichnaea.logging import PingableStatsClient
from ichnaea.tests.base import (
    _make_db,
    _make_redis,
    AppTestCase,
)


class TestMonitor(AppTestCase):

    def test_ok(self):
        app = self.app
        response = app.get('/__monitor__', status=200)
        self.assertEqual(response.content_type, 'application/json')
        data = response.json
        timed_services = set(['database', 'geoip', 'redis', 'stats'])
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
        self.app.app.registry.db_master = self.broken_db
        self.app.app.registry.db_slave = self.broken_db
        # create broken geoip db
        self.app.app.registry.geoip_db = GeoIPNull()
        # create broken redis connection
        redis_uri = 'redis://127.0.0.1:9/15'
        self.broken_redis = _make_redis(redis_uri)
        self.app.app.registry.redis_client = self.broken_redis
        # create broken stats client
        self.broken_stats = PingableStatsClient(host='127.0.0.1', port=0)
        self.app.app.registry.stats_client = self.broken_stats

    def tearDown(self):
        super(TestMonitorErrors, self).tearDown()
        del self.broken_db
        self.broken_redis.connection_pool.disconnect()
        del self.broken_redis
        del self.broken_stats

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

    def test_stats_error(self):
        res = self.app.get('/__monitor__', status=503)
        self.assertEqual(res.content_type, 'application/json')
        self.assertEqual(res.json['stats'], {'up': False, 'time': 0})
