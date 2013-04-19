from unittest import TestCase
from webtest import TestApp

from ichnaea import main


def _make_app():
    global_config = {}
    wsgiapp = main(global_config, database='sqlite://')
    return TestApp(wsgiapp)


class TestSearch(TestCase):

    def test_not_found(self):
        app = _make_app()
        res = app.post('/v1/search',
            '{"cell": [{"mcc": 1, "mnc": 2, "lac": 3, "cid": 4}]}')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.body, '{"status": "not_found"}')


class TestMeasure(TestCase):

    def test_ok(self):
        app = _make_app()
        res = app.post('/v1/location/12.345678/23.456789', '{}')
        self.assertEqual(res.status_code, 204)
        self.assertEqual(res.body, '')


class TestHeartbeat(TestCase):

    def test_ok(self):
        app = _make_app()
        res = app.get('/__heartbeat__')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.body, '{"status": "OK"}')
