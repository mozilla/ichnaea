from unittest import TestCase
from webtest import TestApp

from ichnaea import main
from ichnaea.db import Cell


def _make_app():
    global_config = {}
    wsgiapp = main(global_config, celldb='sqlite://', measuredb='sqlite://')
    return TestApp(wsgiapp)


class TestSearch(TestCase):

    def test_ok(self):
        app = _make_app()
        session = app.app.registry.celldb.session()
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
            {"cell": [{"mcc": 123, "mnc": 1, "lac": 2, "cid": 1234}]},
            status=200)
        self.assertEqual(res.content_type, 'application/json')
        self.assertEqual(res.body, '{"status": "ok", "lat": 12.345678, '
            '"lon": 23.456789, "accuracy": 20000}')

    def test_not_found(self):
        app = _make_app()
        res = app.post_json('/v1/search',
            {"cell": [{"mcc": 1, "mnc": 2, "lac": 3, "cid": 4}]},
            status=200)
        self.assertEqual(res.content_type, 'application/json')
        self.assertEqual(res.body, '{"status": "not_found"}')

    def test_error(self):
        app = _make_app()
        res = app.post_json('/v1/search', {"cell": [{}]}, status=400)
        self.assertEqual(res.content_type, 'application/json')
        self.assertTrue('errors' in res.json)
        self.assertFalse('status' in res.json)

    def test_error_no_data(self):
        app = _make_app()
        res = app.post_json('/v1/search', {"cell": []}, status=400)
        self.assertEqual(res.content_type, 'application/json')
        self.assertTrue('errors' in res.json)

    def test_error_unknown_key(self):
        app = _make_app()
        res = app.post_json('/v1/search', {"foo": 0}, status=400)
        self.assertEqual(res.content_type, 'application/json')
        self.assertTrue('errors' in res.json)

    def test_error_no_mapping(self):
        app = _make_app()
        res = app.post_json('/v1/search', [1], status=400)
        self.assertEqual(res.content_type, 'application/json')
        self.assertTrue('errors' in res.json)

    def test_no_json(self):
        app = _make_app()
        res = app.post('/v1/search', "\xae", status=400)
        self.assertTrue('errors' in res.json)


class TestMeasure(TestCase):

    def test_ok(self):
        app = _make_app()
        res = app.post_json('/v1/location/12.345678/23.456789',
            {"cell": [{"mcc": 123, "mnc": 1, "lac": 2, "cid": 1234}]},
            status=204)
        self.assertEqual(res.body, '')

    def test_error(self):
        app = _make_app()
        res = app.post_json('/v1/location/12.345678/23.456789',
            {"cell": [{}]}, status=400)
        self.assertEqual(res.content_type, 'application/json')
        self.assertTrue('errors' in res.json)
        self.assertFalse('status' in res.json)

    def test_error_no_data(self):
        app = _make_app()
        res = app.post_json('/v1/location/12.345678/23.456789',
            {"cell": []}, status=400)
        self.assertTrue('errors' in res.json)

    def test_error_unknown_key(self):
        app = _make_app()
        res = app.post_json('/v1/location/12.345678/23.456789',
            {"foo": 1}, status=400)
        self.assertTrue('errors' in res.json)

    def test_error_no_mapping(self):
        app = _make_app()
        res = app.post_json('/v1/location/12.345678/23.456789',
            [1], status=400)
        self.assertTrue('errors' in res.json)

    def test_no_json(self):
        app = _make_app()
        res = app.post('/v1/location/12.345678/23.456789', "\xae", status=400)
        self.assertTrue('errors' in res.json)

    def test_invalid_types(self):
        app = _make_app()
        res = app.post('/v1/location/foo/1,2', "\xae", status=400)
        self.assertTrue('errors' in res.json)


class TestHeartbeat(TestCase):

    def test_ok(self):
        app = _make_app()
        res = app.get('/__heartbeat__', status=200)
        self.assertEqual(res.content_type, 'application/json')
        self.assertEqual(res.body, '{"status": "OK"}')
