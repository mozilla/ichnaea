from ichnaea.tests.base import (
    _make_db,
    AppTestCase,
)


class TestHeartbeat(AppTestCase):

    def test_ok(self):
        app = self.app
        res = app.get('/__heartbeat__', status=200)
        self.assertEqual(res.content_type, 'application/json')
        self.assertEqual(res.json['status'], "OK")


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
        self.assertEqual(res.json['status'], "OK")
