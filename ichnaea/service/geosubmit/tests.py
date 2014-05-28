from ichnaea.models import (
    ApiKey,
    Cell,
    CellMeasure,
    Wifi,
    WifiMeasure,
)
from ichnaea.tests.base import CeleryAppTestCase


class TestGeosubmit(CeleryAppTestCase):
    def setUp(self):
        CeleryAppTestCase.setUp(self)
        session = self.db_master_session
        self.app.app.registry.db_slave = self.db_master
        session.add(ApiKey(valid_key='test'))
        session.add(ApiKey(valid_key='test.test'))
        session.commit()

    def test_ok_cell(self):
        app = self.app
        session = self.db_master_session
        cell = Cell()
        cell.lat = 123456781
        cell.lon = 234567892
        cell.radio = 0
        cell.mcc = 123
        cell.mnc = 1
        cell.lac = 2
        cell.cid = 1234
        cell.total_measures = 1
        cell.new_measures = 0

        session.add(cell)
        session.commit()

        res = app.post_json('/v1/geosubmit?key=test', {
                            "latitude": 123456700,
                            "longitude": 234567800,
                            "accuracy": 12.4,
                            "radioType": "gsm",
                            "cellTowers": [{
                                "cellId": 1234,
                                "locationAreaCode": 2,
                                "mobileCountryCode": 123,
                                "mobileNetworkCode": 1,
                            }]},
                            status=200)

        # check that we get back a location
        self.assertEqual(res.content_type, 'application/json')
        self.assertEqual(res.json, {"location": {"lat": 12.3456781,
                                                 "lng": 23.4567892},
                                    "accuracy": 5000})

        cell = session.query(Cell).first()
        self.assertEqual(2, cell.total_measures)
        self.assertEqual(1, cell.new_measures)

        # check that one new CellMeasure record is created
        self.assertEquals(1, session.query(CellMeasure).count())

    def test_ok_no_existing_cell(self):
        app = self.app
        session = self.db_master_session

        res = app.post_json('/v1/geosubmit?key=test', {
                            "latitude": 123456700,
                            "longitude": 234567800,
                            "accuracy": 12.4,
                            "radioType": "gsm",
                            "cellTowers": [{
                                "cellId": 1234,
                                "locationAreaCode": 2,
                                "mobileCountryCode": 123,
                                "mobileNetworkCode": 1,
                            }]},
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

        self.assertEquals(1, session.query(Cell).count())

        # check that one new CellMeasure record is created
        self.assertEquals(1, session.query(CellMeasure).count())

    def test_ok_wifi(self):
        app = self.app
        session = self.db_master_session
        wifis = [
            Wifi(key="0000000000a1", lat=10000000, lon=10000000),
            Wifi(key="0000000000b2", lat=10010000, lon=10020000),
            Wifi(key="0000000000c3", lat=10020000, lon=10040000),
            Wifi(key="0000000000d4", lat=None, lon=None),
        ]
        session.add_all(wifis)
        session.commit()
        res = app.post_json(
            '/v1/geosubmit?key=test', {
                "latitude": 123456700,
                "longitude": 234567800,
                "accuracy": 12.4,
                "radioType": "gsm",
                "wifiAccessPoints": [
                    {"macAddress": "0000000000a1"},
                    {"macAddress": "0000000000b2"},
                    {"macAddress": "0000000000c3"},
                    {"macAddress": "0000000000d4"},
                    {"macAddress": "0000000000e5"},
                ]},
            status=200)
        self.assertEqual(res.content_type, 'application/json')
        self.assertEqual(res.json, {"location": {"lat": 1.0010000,
                                                 "lng": 1.0020000},
                                    "accuracy": 248.60908969845744})

        # Check that e5 exists
        query = session.query(Wifi)
        count = query.filter(Wifi.key == "0000000000e5").count()
        self.assertEquals(1, count)

        # check that WifiMeasure records are created
        self.assertEquals(5, session.query(WifiMeasure).count())

    def test_ok_no_existing_wifi(self):
        app = self.app
        session = self.db_master_session

        res = app.post_json(
            '/v1/geosubmit?key=test', {
                "latitude": 123456700,
                "longitude": 234567800,
                "accuracy": 12.4,
                "radioType": "gsm",
                "wifiAccessPoints": [
                    {"macAddress": "0000000000e5"},
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

        # Check that e5 exists
        query = session.query(Wifi)
        count = query.filter(Wifi.key == "0000000000e5").count()
        self.assertEquals(1, count)

        # check that WifiMeasure records are created
        self.assertEquals(1, session.query(WifiMeasure).count())
