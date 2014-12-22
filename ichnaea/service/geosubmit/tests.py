import time

from ichnaea.models import (
    Cell,
    CellMeasure,
    RADIO_TYPE,
    Wifi,
    WifiMeasure,
)
from ichnaea.tests.base import (
    CeleryAppTestCase,
    FRANCE_MCC,
    PARIS_LAT,
    PARIS_LON,
    PARIS_IP,
)
from ichnaea.service.geolocate.tests import \
    TestGeolocate as GeolocateRegressionTest
from ichnaea.util import utcnow


class TestGeoSubmit(CeleryAppTestCase):

    def setUp(self):
        CeleryAppTestCase.setUp(self)
        self.app.app.registry.db_slave = self.db_master

    def test_ok_cell(self):
        app = self.app
        session = self.db_master_session
        cell = Cell()
        cell.lat = PARIS_LAT + 0.1
        cell.lon = PARIS_LON + 0.1
        cell.radio = 0
        cell.mcc = FRANCE_MCC
        cell.mnc = 1
        cell.lac = 2
        cell.cid = 1234
        cell.total_measures = 1
        cell.new_measures = 0

        session.add(cell)
        session.commit()

        res = app.post_json('/v1/geosubmit?key=test', {
                            "latitude": PARIS_LAT,
                            "longitude": PARIS_LON,
                            "accuracy": 12.4,
                            "radioType": "gsm",
                            "cellTowers": [{
                                "cellId": 1234,
                                "locationAreaCode": 2,
                                "mobileCountryCode": FRANCE_MCC,
                                "mobileNetworkCode": 1,
                            }]},
                            status=200)

        # check that we get back a location
        self.assertEqual(res.content_type, 'application/json')
        self.assertEqual(res.json, {"location": {"lat": PARIS_LAT,
                                                 "lng": PARIS_LON},
                                    "accuracy": 12.4})

        cell = session.query(Cell).first()
        self.assertEqual(2, cell.total_measures)
        self.assertEqual(1, cell.new_measures)

        # check that one new CellMeasure record is created
        self.assertEquals(1, session.query(CellMeasure).count())

        self.check_stats(
            counter=['geosubmit.api_key.test',
                     'items.uploaded.batches',
                     'items.uploaded.reports',
                     'request.v1.geosubmit.200',
                     ],
            timer=['items.uploaded.batch_size',
                   'request.v1.geosubmit'])

    def test_ok_no_existing_cell(self):
        app = self.app
        session = self.db_master_session
        now_ms = int(time.time() * 1000)
        first_of_month = utcnow().replace(day=1, hour=0, minute=0, second=0)

        res = app.post_json('/v1/geosubmit?key=test', {
                            "latitude": PARIS_LAT,
                            "longitude": PARIS_LON,
                            "accuracy": 12.4,
                            "altitude": 100.1,
                            "altitudeAccuracy": 23.7,
                            "heading": 45.0,
                            "speed": 3.6,
                            "timestamp": now_ms,
                            "radioType": "gsm",
                            "cellTowers": [{
                                "cellId": 1234,
                                "locationAreaCode": 2,
                                "mobileCountryCode": FRANCE_MCC,
                                "mobileNetworkCode": 1,
                                "age": 3,
                                "asu": 31,
                                "psc": 15,
                                "signalStrength": -51,
                                "timingAdvance": 1,
                            }]},
                            status=200)

        self.assertEqual(res.content_type, 'application/json')
        self.assertEqual(res.json, {"location": {"lat": PARIS_LAT,
                                                 "lng": PARIS_LON},
                                    "accuracy": 12.4})

        self.assertEquals(session.query(Cell).count(), 1)

        # check that one new CellMeasure record is created
        result = session.query(CellMeasure).all()
        self.assertEquals(len(result), 1)
        measure = result[0]
        self.assertEqual(measure.lat, PARIS_LAT)
        self.assertEqual(measure.lon, PARIS_LON)
        self.assertEqual(measure.accuracy, 12)
        self.assertEqual(measure.altitude, 100)
        self.assertEqual(measure.altitude_accuracy, 24)
        self.assertEqual(measure.heading, 45.0)
        self.assertEqual(measure.speed, 3.6)
        self.assertEqual(measure.time, first_of_month)
        self.assertEqual(measure.radio, RADIO_TYPE['gsm'])
        self.assertEqual(measure.mcc, FRANCE_MCC)
        self.assertEqual(measure.mnc, 1)
        self.assertEqual(measure.lac, 2)
        self.assertEqual(measure.cid, 1234)
        self.assertEqual(measure.psc, 15)
        self.assertEqual(measure.asu, 31)
        self.assertEqual(measure.signal, -51)
        self.assertEqual(measure.ta, 1)

    def test_ok_wifi(self):
        app = self.app
        session = self.db_master_session
        wifis = [
            Wifi(key="101010101010", lat=1.0, lon=1.0),
            Wifi(key="202020202020", lat=1.001, lon=1.002),
            Wifi(key="303030303030", lat=1.002, lon=1.004),
            Wifi(key="404040404040", lat=None, lon=None),
        ]
        session.add_all(wifis)
        session.commit()
        res = app.post_json(
            '/v1/geosubmit?key=test', {
                "latitude": 12.34567,
                "longitude": 23.45678,
                "accuracy": 12.4,
                "radioType": "gsm",
                "wifiAccessPoints": [
                    {"macAddress": "101010101010"},
                    {"macAddress": "202020202020"},
                    {"macAddress": "303030303030"},
                    {"macAddress": "404040404040"},
                    {"macAddress": "505050505050"},
                ]},
            status=200)
        self.assertEqual(res.content_type, 'application/json')
        self.assertEqual(res.json, {"location": {"lat": 12.34567,
                                                 "lng": 23.45678},
                                    "accuracy": 12.4})

        # Check that 505050505050 exists
        query = session.query(Wifi)
        count = query.filter(Wifi.key == "505050505050").count()
        self.assertEquals(1, count)

        # check that WifiMeasure records are created
        self.assertEquals(5, session.query(WifiMeasure).count())

    def test_ok_no_existing_wifi(self):
        app = self.app
        session = self.db_master_session

        res = app.post_json(
            '/v1/geosubmit?key=test', {
                "latitude": PARIS_LAT,
                "longitude": PARIS_LON,
                "accuracy": 12.4,
                "radioType": "gsm",
                "wifiAccessPoints": [{
                    "macAddress": "505050505050",
                    "age": 3,
                    "channel": 6,
                    "frequency": 2437,
                    "signalToNoiseRatio": 13,
                    "signalStrength": -77,
                }]},
            status=200)

        self.assertEqual(res.content_type, 'application/json')
        self.assertEqual(res.json, {"location": {"lat": PARIS_LAT,
                                                 "lng": PARIS_LON},
                                    "accuracy": 12.4})

        # Check that 505050505050 exists
        query = session.query(Wifi)
        count = query.filter(Wifi.key == "505050505050").count()
        self.assertEquals(count, 1)

        # check that WifiMeasure records are created
        result = session.query(WifiMeasure).all()
        self.assertEquals(len(result), 1)
        measure = result[0]
        self.assertEqual(measure.lat, PARIS_LAT)
        self.assertEqual(measure.lon, PARIS_LON)
        self.assertEqual(measure.channel, 6)
        self.assertEqual(measure.signal, -77)
        self.assertEqual(measure.snr, 13)

    def test_geoip_match(self):
        app = self.app
        session = self.db_master_session

        res = app.post_json('/v1/geosubmit?key=test', {
                            "latitude": PARIS_LAT,
                            "longitude": PARIS_LON,
                            "accuracy": 12.4,
                            "radioType": "gsm",
                            "cellTowers": [{
                                "cellId": 1234,
                                "locationAreaCode": 2,
                                "mobileCountryCode": FRANCE_MCC,
                                "mobileNetworkCode": 1,
                            }]},
                            extra_environ={'HTTP_X_FORWARDED_FOR': PARIS_IP},
                            status=200)

        self.assertEqual(res.content_type, 'application/json')
        self.assertEqual(res.json, {"location": {"lat": PARIS_LAT,
                                                 "lng": PARIS_LON},
                                    "accuracy": 12.4})

        self.assertEquals(1, session.query(Cell).count())

        # check that one new CellMeasure record is created
        self.assertEquals(1, session.query(CellMeasure).count())


class TestGeoSubmitBatch(CeleryAppTestCase):

    def setUp(self):
        CeleryAppTestCase.setUp(self)
        self.app.app.registry.db_slave = self.db_master

    def test_ok_cell(self):
        app = self.app
        session = self.db_master_session
        cell = Cell()
        cell.lat = PARIS_LAT
        cell.lon = PARIS_LON
        cell.radio = 0
        cell.mcc = FRANCE_MCC
        cell.mnc = 1
        cell.lac = 2
        cell.cid = 1234
        cell.total_measures = 1
        cell.new_measures = 0

        session.add(cell)
        session.commit()

        res = app.post_json('/v1/geosubmit?key=test',
                            {'items': [{"latitude": PARIS_LAT + 0.1,
                                        "longitude": PARIS_LON + 0.1,
                                        "accuracy": 12.4,
                                        "radioType": "gsm",
                                        "cellTowers": [{
                                            "cellId": 1234,
                                            "locationAreaCode": 2,
                                            "mobileCountryCode": FRANCE_MCC,
                                            "mobileNetworkCode": 1,
                                        }]},
                                       {"latitude": PARIS_LAT - 0.1,
                                        "longitude": PARIS_LON - 0.1,
                                        "accuracy": 22.4,
                                        "radioType": "gsm",
                                        "cellTowers": [{
                                            "cellId": 2234,
                                            "locationAreaCode": 22,
                                            "mobileCountryCode": FRANCE_MCC,
                                            "mobileNetworkCode": 2,
                                        }]}]},
                            status=200)

        # check that we get an empty response
        self.assertEqual(res.content_type, 'application/json')
        self.assertEqual(res.json, {})

        # check that two new CellMeasure records are created
        self.assertEquals(2, session.query(CellMeasure).count())
        cm1 = session.query(CellMeasure).filter(
            CellMeasure.cid == 1234).count()
        cm2 = session.query(CellMeasure).filter(
            CellMeasure.cid == 2234).count()
        self.assertEquals(1, cm1)
        self.assertEquals(1, cm2)

        self.check_stats(
            counter=['geosubmit.api_key.test',
                     'items.uploaded.batches',
                     'items.uploaded.reports',
                     ],
            timer=['items.uploaded.batch_size'])

    def test_geoip_match(self):
        app = self.app
        session = self.db_master_session
        cell = Cell()
        cell.lat = PARIS_LAT
        cell.lon = PARIS_LON
        cell.radio = 0
        cell.mcc = FRANCE_MCC
        cell.mnc = 1
        cell.lac = 2
        cell.cid = 1234
        cell.total_measures = 1
        cell.new_measures = 0

        session.add(cell)
        session.commit()

        res = app.post_json('/v1/geosubmit?key=test',
                            {'items': [{"latitude": PARIS_LAT + 0.1,
                                        "longitude": PARIS_LON + 0.1,
                                        "accuracy": 12.4,
                                        "radioType": "gsm",
                                        "cellTowers": [{
                                            "cellId": 1234,
                                            "locationAreaCode": 2,
                                            "mobileCountryCode": FRANCE_MCC,
                                            "mobileNetworkCode": 1,
                                        }]},
                                       {"latitude": PARIS_LAT - 0.1,
                                        "longitude": PARIS_LON - 0.1,
                                        "accuracy": 22.4,
                                        "radioType": "gsm",
                                        "cellTowers": [{
                                            "cellId": 2234,
                                            "locationAreaCode": 22,
                                            "mobileCountryCode": FRANCE_MCC,
                                            "mobileNetworkCode": 2,
                                        }]}]},
                            extra_environ={'HTTP_X_FORWARDED_FOR': PARIS_IP},
                            status=200)

        # check that we get an empty response
        self.assertEqual(res.content_type, 'application/json')
        self.assertEqual(res.json, {})

        # check that two new CellMeasure records are created
        self.assertEquals(2, session.query(CellMeasure).count())
        cm1 = session.query(CellMeasure).filter(
            CellMeasure.cid == 1234).count()
        cm2 = session.query(CellMeasure).filter(
            CellMeasure.cid == 2234).count()
        self.assertEquals(1, cm1)
        self.assertEquals(1, cm2)


class TestGeolocateRegression(GeolocateRegressionTest, CeleryAppTestCase):

    def setUp(self):
        CeleryAppTestCase.setUp(self)
        self.app.app.registry.db_slave = self.db_master

        self.url = '/v1/geosubmit'
        self.metric = 'geosubmit'
        self.metric_url = 'request.v1.geosubmit'

    def get_session(self):
        return self.db_master_session
