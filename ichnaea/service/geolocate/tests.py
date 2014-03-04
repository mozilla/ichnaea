from ichnaea.models import (
    Cell,
    Wifi,
)
from ichnaea.tests.base import AppTestCase
import json


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

        find_msg = self.find_heka_messages
        self.assertEquals(
            len(find_msg('counter', 'http.request')), 1)
        self.assertEqual(1, len(find_msg('counter', 'geolocate.api_key.test')))

        self.assertEqual(res.content_type, 'application/json')
        self.assertEqual(res.body, '{"location": {"lat": 12.3456781, '
                                   '"lng": 23.4567892}, "accuracy": 35000.0}')

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
        find_msg = self.find_heka_messages
        self.assertEqual(1, len(find_msg('counter', 'geolocate.api_key.test')))
        self.assertEqual(res.content_type, 'application/json')
        self.assertEqual(res.body, '{"location": {"lat": 1.0010000, '
                                   '"lng": 1.0020000}, "accuracy": 500.0}')

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

        find_msg = self.find_heka_messages
        self.assertEqual(1, len(find_msg('counter', 'geolocate.api_key.test')))

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

        find_msg = self.find_heka_messages
        expected_key = 'geolocate.api_key.test__test'
        self.assertEqual(1, len(find_msg('counter', expected_key)))

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
