from unittest import TestCase
from webtest import TestApp

from ichnaea import main
from ichnaea.db import Cell, Measure
from ichnaea.renderer import dump_decimal_json


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
        cell.radio = 0
        cell.mcc = 123
        cell.mnc = 1
        cell.lac = 2
        cell.cid = 1234
        session.add(cell)
        session.commit()

        res = app.post_json('/v1/search',
                            {"radio": "gsm",
                             "cell": [{"mcc": 123, "mnc": 1,
                                       "lac": 2, "cid": 1234}]},
                            status=200)
        self.assertEqual(res.content_type, 'application/json')
        self.assertEqual(res.body, '{"status": "ok", "lat": 12.345678, '
                                   '"lon": 23.456789, "accuracy": 20000}')

    def test_not_found(self):
        app = _make_app()
        res = app.post_json('/v1/search',
                            {"cell": [{"mcc": 1, "mnc": 2,
                                       "lac": 3, "cid": 4}]},
                            status=200)
        self.assertEqual(res.content_type, 'application/json')
        self.assertEqual(res.body, '{"status": "not_found"}')

    def test_one_wifi(self):
        app = _make_app()
        res = app.post_json('/v1/search',
                            {"wifi": [{"mac": "ab:cd:12:34"}]},
                            status=400)
        self.assertEqual(res.content_type, 'application/json')
        self.assertTrue('errors' in res.json)

    def test_wifi_not_found(self):
        app = _make_app()
        res = app.post_json('/v1/search', {"wifi": [
                            {"mac": "ab:cd:12:34"}, {"mac": "cd:ef:23:45"}]},
                            status=200)
        self.assertEqual(res.content_type, 'application/json')
        self.assertEqual(res.body, '{"status": "not_found"}')

    def test_error(self):
        app = _make_app()
        res = app.post_json('/v1/search', {"cell": []}, status=400)
        self.assertEqual(res.content_type, 'application/json')
        self.assertTrue('errors' in res.json)
        self.assertFalse('status' in res.json)

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

    def test_ok_cell(self):
        app = _make_app()
        cell_data = [{"mcc": 123, "mnc": 1, "lac": 2, "cid": 1234}]
        res = app.post_json('/v1/submit',
                            {"lat": 12.345678, "lon": 23.456789,
                             "radio": "gsm", "cell": cell_data}, status=204)
        self.assertEqual(res.body, '')
        session = app.app.registry.measuredb.session()
        result = session.query(Measure).all()
        self.assertEqual(len(result), 1)
        item = result[0]
        self.assertEqual(item.lat, 12345678)
        self.assertEqual(item.lon, 23456789)
        # colander schema adds default value
        cell_data[0]['signal'] = 0
        self.assertEqual(item.cell, dump_decimal_json(cell_data))
        self.assertTrue(item.wifi is None)

    def test_ok_wifi(self):
        app = _make_app()
        wifi_data = [{"mac": "ab:12:34"}, {"mac": "cd:34:56"}]
        res = app.post_json('/v1/submit',
                            {"lat": 12.345678, "lon": 23.456789,
                             "wifi": wifi_data}, status=204)
        self.assertEqual(res.body, '')
        session = app.app.registry.measuredb.session()
        result = session.query(Measure).all()
        self.assertEqual(len(result), 1)
        item = result[0]
        self.assertEqual(item.lat, 12345678)
        self.assertEqual(item.lon, 23456789)
        # colander schema adds default values
        for i in range(2):
            wifi_data[i]['channel'] = 0
            wifi_data[i]['noise'] = 0
            wifi_data[i]['signal'] = 0
        self.assertEqual(item.wifi, dump_decimal_json(wifi_data))
        self.assertTrue(item.cell is None)

    def test_error(self):
        app = _make_app()
        res = app.post_json('/v1/submit',
                            {"lat": 12.3, "lon": 23.4, "cell": []}, status=400)
        self.assertEqual(res.content_type, 'application/json')
        self.assertTrue('errors' in res.json)
        self.assertFalse('status' in res.json)

    def test_error_unknown_key(self):
        app = _make_app()
        res = app.post_json('/v1/submit',
                            {"lat": 12.3, "lon": 23.4, "foo": 1}, status=400)
        self.assertTrue('errors' in res.json)

    def test_error_no_mapping(self):
        app = _make_app()
        res = app.post_json('/v1/submit', [1], status=400)
        self.assertTrue('errors' in res.json)

    def test_no_json(self):
        app = _make_app()
        res = app.post('/v1/submit', "\xae", status=400)
        self.assertTrue('errors' in res.json)


class TestHeartbeat(TestCase):

    def test_ok(self):
        app = _make_app()
        res = app.get('/__heartbeat__', status=200)
        self.assertEqual(res.content_type, 'application/json')
        self.assertEqual(res.body, '{"status": "OK"}')
