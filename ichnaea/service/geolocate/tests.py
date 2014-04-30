import json

from ichnaea.models import (
    Cell,
    Wifi,
    CELLID_LAC,
)
from ichnaea.heka_logging import RAVEN_ERROR
from ichnaea.tests.base import AppTestCase


class TestGeolocate(AppTestCase):

    def test_ok_cell(self):
        app = self.app
        session = self.db_slave_session
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

        res = app.post_json(
            '/v1/geolocate?key=test', {
                "radioType": "gsm",
                "cellTowers": [
                    {"mobileCountryCode": 123, "mobileNetworkCode": 1,
                     "locationAreaCode": 2, "cellId": 1234},
                ]},
            status=200)

        self.check_expected_heka_messages(
            counter=['http.request', 'geolocate.api_key.test']
        )

        self.assertEqual(res.content_type, 'application/json')
        self.assertEqual(res.json, {"location": {"lat": 12.3456781,
                                                 "lng": 23.4567892},
                                    "accuracy": 35000.0})

    def test_ok_wifi(self):
        app = self.app
        session = self.db_slave_session
        wifis = [
            Wifi(key="a1", lat=10000000, lon=10000000),
            Wifi(key="b2", lat=10010000, lon=10020000),
            Wifi(key="c3", lat=10020000, lon=10040000),
            Wifi(key="d4", lat=None, lon=None),
        ]
        session.add_all(wifis)
        session.commit()
        res = app.post_json(
            '/v1/geolocate?key=test', {
                "wifiAccessPoints": [
                    {"macAddress": "a1"},
                    {"macAddress": "b2"},
                    {"macAddress": "c3"},
                    {"macAddress": "d4"},
                ]},
            status=200)
        self.check_expected_heka_messages(counter=['geolocate.api_key.test'])
        self.assertEqual(res.content_type, 'application/json')
        self.assertEqual(res.json, {"location": {"lat": 1.0010000,
                                                 "lng": 1.0020000},
                                    "accuracy": 500.0})

    def test_wifi_not_found(self):
        app = self.app
        res = app.post_json(
            '/v1/geolocate?key=test', {
                "wifiAccessPoints": [
                    {"macAddress": "abcd"}, {"macAddress": "cdef"},
                ]},
            status=404)
        self.assertEqual(res.content_type, 'application/json')
        self.assertEqual(
            res.json, {"error": {
                "errors": [{
                    "domain": "geolocation",
                    "reason": "notFound",
                    "message": "Not found",
                }],
                "code": 404,
                "message": "Not found"
            }}
        )

        # Make sure to get two counters, a timer, and no traceback
        self.check_expected_heka_messages(
            counter=['geolocate.api_key.test',
                     'http.request'],
            timer=['http.request'],
            sentry=[('msg', RAVEN_ERROR, 0)]
        )

    def test_cell_miss_lac_hit(self):
        app = self.app
        session = self.db_slave_session
        key = dict(mcc=1, mnc=2, lac=3)
        data = [
            Cell(lat=10000000, lon=10000000, radio=2, cid=4, **key),
            Cell(lat=10020000, lon=10040000, radio=2, cid=5, **key),
            Cell(lat=10060000, lon=10060000, radio=2, cid=6, **key),
            Cell(lat=10026666, lon=10033333, radio=2, cid=CELLID_LAC,
                 range=50000, **key),
        ]
        session.add_all(data)
        session.commit()

        res = app.post_json(
            '/v1/geolocate?key=test',
            {'radioType': 'wcdma',
             'cellTowers': [
                 {'cellId': 7,
                  'mobileCountryCode': 1,
                  'mobileNetworkCode': 2,
                  'locationAreaCode': 3}]},
            status=200)
        self.assertEqual(res.content_type, 'application/json')
        self.assertEqual(res.json, {'location': {"lat": 1.0026666,
                                                 "lng": 1.0033333},
                                    "accuracy": 50000.0})

    def test_cell_hit_ignores_lac(self):
        app = self.app
        session = self.db_slave_session
        key = dict(mcc=1, mnc=2, lac=3)
        data = [
            Cell(lat=10000000, lon=10000000, radio=2, cid=4, **key),
            Cell(lat=10020000, lon=10040000, radio=2, cid=5, **key),
            Cell(lat=10060000, lon=10060000, radio=2, cid=6, **key),
            Cell(lat=10026666, lon=10033333, radio=2, cid=CELLID_LAC,
                 range=50000, **key),
        ]
        session.add_all(data)
        session.commit()

        res = app.post_json(
            '/v1/geolocate?key=test',
            {'radioType': 'wcdma',
             'cellTowers': [
                 {'cellId': 5,
                  'mobileCountryCode': 1,
                  'mobileNetworkCode': 2,
                  'locationAreaCode': 3}]},
            status=200)
        self.assertEqual(res.content_type, 'application/json')
        self.assertEqual(res.json, {'location': {"lat": 1.0020000,
                                                 "lng": 1.0040000},
                                    "accuracy": 35000.0})

    def test_lac_miss(self):
        app = self.app
        session = self.db_slave_session
        key = dict(mcc=1, mnc=2, lac=3)
        data = [
            Cell(lat=10000000, lon=10000000, radio=2, cid=4, **key),
            Cell(lat=10020000, lon=10040000, radio=2, cid=5, **key),
            Cell(lat=10060000, lon=10060000, radio=2, cid=6, **key),
            Cell(lat=10026666, lon=10033333, radio=2, cid=CELLID_LAC,
                 range=50000, **key),
        ]
        session.add_all(data)
        session.commit()

        res = app.post_json(
            '/v1/geolocate?key=test',
            {'radioType': 'wcdma',
             'cellTowers': [
                 {'cellId': 5,
                  'mobileCountryCode': 1,
                  'mobileNetworkCode': 2,
                  'locationAreaCode': 4}]},
            status=404)
        self.assertEqual(
            res.json, {"error": {
                "errors": [{
                    "domain": "geolocation",
                    "reason": "notFound",
                    "message": "Not found",
                }],
                "code": 404,
                "message": "Not found"
            }}
        )

    def test_geoip_fallback(self):
        app = self.app

        res = app.post_json(
            '/v1/geolocate?key=test',
            {"wifiAccessPoints": [
                {"macAddress": "Porky"}, {"macAddress": "Piggy"},
                {"macAddress": "Davis"}, {"macAddress": "McSnappy"},
            ]},
            extra_environ={'HTTP_X_FORWARDED_FOR': '66.92.181.240'},
            status=200)
        self.assertEqual(res.content_type, 'application/json')
        self.assertEqual(res.json, {"location": {"lat": 37.5079,
                                                 "lng": -121.96},
                                    "accuracy": 40000.0})

    def test_parse_error(self):
        app = self.app
        res = app.post_json(
            '/v1/geolocate?key=test.test', {
                "wifiAccessPoints": [
                    {"nomac": 1},
                ]},
            status=400)
        self.assertEqual(res.content_type, 'application/json')
        self.assertEqual(
            res.json, {"error": {
                "errors": [{
                    "domain": "global",
                    "reason": "parseError",
                    "message": "Parse Error",
                }],
                "code": 400,
                "message": "Parse Error"
            }}
        )

        self.check_expected_heka_messages(
            counter=['geolocate.api_key.test__test']
        )

    def test_no_data(self):
        app = self.app
        res = app.post_json(
            '/v1/geolocate?key=test', {"wifiAccessPoints": []},
            status=400)
        self.assertEqual(res.content_type, 'application/json')

    def test_no_api_key(self):
        app = self.app
        session = self.db_slave_session
        wifis = [
            Wifi(key="a1", lat=10000000, lon=10000000, total_measures=9),
            Wifi(key="b2", lat=10010000, lon=10020000, total_measures=9),
            Wifi(key="c3", lat=10020000, lon=10040000, total_measures=9),
        ]
        session.add_all(wifis)
        session.commit()
        res = app.post_json(
            '/v1/geolocate', {
                "wifiAccessPoints": [
                    {"macAddress": "a1"},
                    {"macAddress": "b2"},
                    {"macAddress": "c3"},
                ]},
            status=400)

        json_err = json.loads(res.body)
        self.assertEqual(u'No API key', json_err['error']['message'])
        self.assertEqual(res.content_type, 'application/json')

        self.check_expected_heka_messages(counter=['geolocate.no_api_key'])
