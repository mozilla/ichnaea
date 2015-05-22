from ichnaea.config import DummyConfig
from ichnaea.tests.base import (
    _make_app,
    _make_db,
    DBTestCase,
    RedisIsolation,
    REDIS_URI,
    SQLURI,
)


class TestApp(RedisIsolation, DBTestCase):

    def test_db_config(self):
        app_config = DummyConfig({'ichnaea': {
            'db_master': SQLURI,
            'db_slave': SQLURI,
        }})
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
        app_config = DummyConfig({'ichnaea': {
            'redis_url': REDIS_URI,
        }})
        app = _make_app(app_config=app_config,
                        _db_rw=self.db_rw,
                        _db_ro=self.db_ro,
                        _raven_client=self.raven_client,
                        _stats_client=self.stats_client)
        redis_client = app.app.registry.redis_client
        self.assertTrue(redis_client is not None)
        self.assertEqual(
            redis_client.connection_pool.connection_kwargs['db'], 1)
