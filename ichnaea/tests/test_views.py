from datetime import datetime
from unittest2 import TestCase
from webtest import TestApp

from ichnaea import main
from ichnaea.db import Cell, Measure
from ichnaea.decimaljson import loads


def _make_app():
    global_config = {}
    wsgiapp = main(global_config, celldb='sqlite://', measuredb='sqlite://',
                   batch_size=-1)
    return TestApp(wsgiapp)


class TestSearch(TestCase):

    def test_ok(self):
        app = _make_app()
        session = app.app.registry.celldb.session()
        cell = Cell()
        cell.lat = 123456781
        cell.lon = 234567892
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
        self.assertEqual(res.body, '{"status": "ok", "lat": 12.3456781, '
                                   '"lon": 23.4567892, "accuracy": 35000}')

    def test_not_found(self):
        app = _make_app()
        res = app.post_json('/v1/search',
                            {"cell": [{"mcc": 1, "mnc": 2,
                                       "lac": 3, "cid": 4}]},
                            status=200)
        self.assertEqual(res.content_type, 'application/json')
        self.assertEqual(res.body, '{"status": "not_found"}')

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
        self.assertTrue('status' in res.json)
        self.assertEquals(res.json['status'], 'error')

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
        res = app.post_json(
            '/v1/submit', {"items": [{"lat": 12.3456781,
                                      "lon": 23.4567892,
                                      "accuracy": 10,
                                      "altitude": 123,
                                      "altitude_accuracy": 7,
                                      "radio": "gsm",
                                      "cell": cell_data}]},
            status=204)
        self.assertEqual(res.body, '')
        session = app.app.registry.measuredb.session()
        result = session.query(Measure).all()
        self.assertEqual(len(result), 1)
        item = result[0]
        self.assertEqual(item.lat, 123456781)
        self.assertEqual(item.lon, 234567892)
        self.assertEqual(item.accuracy, 10)
        self.assertEqual(item.altitude, 123)
        self.assertEqual(item.altitude_accuracy, 7)
        # colander schema adds default value
        cell_data[0]['psc'] = 0
        cell_data[0]['asu'] = 0
        cell_data[0]['signal'] = 0
        cell_data[0]['ta'] = 0

        wanted = loads(item.cell)
        self.assertTrue(len(wanted), 1)
        self.assertTrue(len(cell_data), 1)
        self.assertDictEqual(wanted[0], cell_data[0])
        self.assertTrue(item.wifi is None)

    def test_ok_wifi(self):
        app = _make_app()
        wifi_data = [{"mac": "ab:12:34"}, {"mac": "cd:34:56"}]
        res = app.post_json(
            '/v1/submit', {"items": [{"lat": 12.3456781,
                                      "lon": 23.4567892,
                                      "accuracy": 17,
                                      "wifi": wifi_data}]},
            status=204)
        self.assertEqual(res.body, '')
        session = app.app.registry.measuredb.session()
        result = session.query(Measure).all()
        self.assertEqual(len(result), 1)
        item = result[0]
        self.assertEqual(item.lat, 123456781)
        self.assertEqual(item.lon, 234567892)
        self.assertEqual(item.accuracy, 17)
        self.assertEqual(item.altitude, 0)
        self.assertEqual(item.altitude_accuracy, 0)
        self.assertTrue('"mac": "ab:12:34"' in item.wifi)
        self.assertTrue('"mac": "cd:34:56"' in item.wifi)
        self.assertTrue(item.cell is None)

    def test_ok_wifi_frequency(self):
        app = _make_app()
        wifi_data = [
            {"mac": "99"},
            {"mac": "aa", "frequency": 2427},
            {"mac": "bb", "channel": 7},
            {"mac": "cc", "frequency": 5200},
            {"mac": "dd", "frequency": 5700},
            {"mac": "ee", "frequency": 3100},
            {"mac": "ff", "frequency": 2412, "channel": 9},
        ]
        res = app.post_json(
            '/v1/submit', {"items": [{"lat": 12.345678,
                                      "lon": 23.456789,
                                      "wifi": wifi_data}]},
            status=204)
        self.assertEqual(res.body, '')
        session = app.app.registry.measuredb.session()
        result = session.query(Measure).all()
        self.assertEqual(len(result), 1)
        item = result[0]
        measure_wifi = loads(item.wifi)
        measure_wifi = dict([(m['mac'], m) for m in measure_wifi])
        for k, v in measure_wifi.items():
            self.assertFalse('frequency' in v)
        self.assertEqual(measure_wifi['99']['channel'], 0)
        self.assertEqual(measure_wifi['aa']['channel'], 4)
        self.assertEqual(measure_wifi['bb']['channel'], 7)
        self.assertEqual(measure_wifi['cc']['channel'], 40)
        self.assertEqual(measure_wifi['dd']['channel'], 140)
        self.assertEqual(measure_wifi['ee']['channel'], 0)
        self.assertEqual(measure_wifi['ff']['channel'], 9)

    def test_batches(self):
        app = _make_app()
        wifi_data = [{"mac": "aa"}, {"mac": "bb"}]
        items = [{"lat": 12.34, "lon": 23.45 + i, "wifi": wifi_data}
                 for i in range(10)]
        res = app.post_json('/v1/submit', {"items": items}, status=204)
        self.assertEqual(res.body, '')

        # let's add a bad one
        items.append({'whatever': 'xx'})
        res = app.post_json('/v1/submit', {"items": items}, status=400)

    def test_time(self):
        app = _make_app()
        time = "2012-03-15T11:12:13.456Z"
        app.post_json(
            '/v1/submit', {"items": [
                {"lat": 1.0, "lon": 2.0, "wifi": [{"mac": "a"}], "time": time},
                {"lat": 2.0, "lon": 3.0, "wifi": [{"mac": "b"}]},
            ]},
            status=204)
        session = app.app.registry.measuredb.session()
        result = session.query(Measure).all()
        self.assertEqual(len(result), 2)
        for item in result:
            if '"mac": "a"' in item.wifi:
                self.assertEqual(
                    item.time, datetime(2012, 3, 15, 11, 12, 13, 456000))
            else:
                self.assertEqual(
                    item.time.date(), datetime.utcnow().date())

    def test_error(self):
        app = _make_app()
        res = app.post_json(
            '/v1/submit', {"items": [{"lat": 12.3, "lon": 23.4, "cell": []}]},
            status=400)
        self.assertEqual(res.content_type, 'application/json')
        self.assertTrue('errors' in res.json)
        self.assertEquals(res.json['status'], 'error')

    def test_error_unknown_key(self):
        app = _make_app()
        res = app.post_json(
            '/v1/submit', {"items": [{"lat": 12.3, "lon": 23.4, "foo": 1}]},
            status=400)
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
