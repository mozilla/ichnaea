from unittest import TestCase
from webtest import TestApp

from ichnaea import main
from ichnaea.db import Cell


def _make_app():
    global_config = {}
    wsgiapp = main(global_config, database='sqlite://')
    return TestApp(wsgiapp)


class TestSearch(TestCase):

    def test_ok(self):
        app = _make_app()
        session = app.app.registry.db.session()
        cell = Cell()
        cell.lat = 12345678
        cell.lon = 23456789
        cell.mcc = 123
        cell.mnc = 1
        cell.lac = 2
        cell.cid = 1234
        session.add(cell)
        session.commit()

        res = app.post_json('/v1/search',
            {"cell": [{"mcc": 123, "mnc": 1, "lac": 2, "cid": 1234}]})
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.content_type, 'application/json')
        self.assertEqual(res.body, '{"status": "ok", "lat": 12.345678, '
            '"lon": 23.456789, "accuracy": 20000}')

    def test_not_found(self):
        app = _make_app()
        res = app.post_json('/v1/search',
            {"cell": [{"mcc": 1, "mnc": 2, "lac": 3, "cid": 4}]})
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.content_type, 'application/json')
        self.assertEqual(res.body, '{"status": "not_found"}')

    def test_error(self):
        app = _make_app()
        res = app.post_json('/v1/search', {"cell": [{}]}, expect_errors=True)
        self.assertEqual(res.status_code, 400)
        self.assertEqual(res.content_type, 'application/json')
        self.assertTrue('errors' in res.json)
        self.assertFalse('status' in res.json)


class TestMeasure(TestCase):

    def test_ok(self):
        app = _make_app()
        res = app.post_json('/v1/location/12.345678/23.456789',
            {"cell": [{"mcc": 123, "mnc": 1, "lac": 2, "cid": 1234}]})
        self.assertEqual(res.status_code, 204)
        self.assertEqual(res.body, '')


class TestHeartbeat(TestCase):

    def test_ok(self):
        app = _make_app()
        res = app.get('/__heartbeat__')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.content_type, 'application/json')
        self.assertEqual(res.body, '{"status": "OK"}')
