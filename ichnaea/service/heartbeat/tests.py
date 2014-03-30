from ichnaea.db import _VolatileModel, _ArchivalModel
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

        # create database connections to the discard ports
        self.app.app.registry.volatile_db = _make_db(
            _VolatileModel,
            uri='mysql+pymysql://none:none@127.0.0.1:9/test_location_volatile',
            socket=None,
            create=False,
        )
        self.app.app.registry.archival_db = _make_db(
            _ArchivalModel,
            uri='mysql+pymysql://none:none@127.0.0.1:9/test_location_archival',
            socket=None,
            create=False,
        )

        res = app.get('/__heartbeat__', status=503)
        self.assertEqual(res.content_type, 'text/plain')
