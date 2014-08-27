from ichnaea.tests.base import (
    _make_app,
    _make_db,
    DBTestCase,
    RedisIsolation,
    REDIS_URI,
    SQLURI,
)


class TestApp(DBTestCase, RedisIsolation):

    @classmethod
    def setUpClass(cls):
        super(TestApp, cls).setUpClass()
        super(TestApp, cls).setup_redis()

    @classmethod
    def tearDownClass(cls):
        super(TestApp, cls).tearDownClass()
        super(TestApp, cls).teardown_redis()

    def tearDown(self):
        super(TestApp, self).tearDown()
        self.cleanup_redis()

    def test_db_hooks(self):
        settings = {
            'db_master': SQLURI,
            'db_slave': SQLURI,
        }
        app = _make_app(_heka_client=self.heka_client,
                        _stats_client=self.stats_client,
                        _redis=self.redis_client,
                        **settings)
        self.db_master = app.app.registry.db_master
        self.db_slave = app.app.registry.db_slave
        self.setup_session()
        app.get('/stats_unique_cell.json', status=200)

    def test_db_config(self):
        self.db_master = _make_db()
        self.db_slave = _make_db()
        self.setup_session()
        app = _make_app(_db_master=self.db_master,
                        _db_slave=self.db_slave,
                        _heka_client=self.heka_client,
                        _stats_client=self.stats_client,
                        _redis=self.redis_client,
                        )
        app.get('/stats_unique_cell.json', status=200)

    def test_redis_config(self):
        settings = {
            'db_master': SQLURI,
            'db_slave': SQLURI,
            'redis_url': REDIS_URI,
        }
        app = _make_app(_heka_client=self.heka_client,
                        _stats_client=self.stats_client, **settings)
        self.assertTrue(app.app.registry.redis_client is not None)
