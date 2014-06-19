from ichnaea.tests.base import (
    _make_app,
    _make_db,
    DBTestCase,
    REDIS_URI,
    SQLURI,
)


class TestApp(DBTestCase):

    def test_db_hooks(self):
        settings = {
            'db_master': SQLURI,
            'db_slave': SQLURI,
            'redis_url': REDIS_URI,
            '_heka_client': self.heka_client,
        }
        app = _make_app(**settings)
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
                        )
        app.get('/stats_unique_cell.json', status=200)

    def test_redis_config(self):
        settings = {
            'db_master': SQLURI,
            'db_slave': SQLURI,
            'redis_url': REDIS_URI,
            '_heka_client': self.heka_client,
        }
        app = _make_app(**settings)
        self.assertTrue(app.app.registry.redis_con is not None)
