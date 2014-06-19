from ichnaea.models import (
    Cell,
    CellMeasure,
    Wifi,
    WifiMeasure,
    from_degrees,
)
from ichnaea.tests.base import (
    CeleryAppTestCase,
    FRANCE_MCC,
    PARIS_LAT,
    PARIS_LON,
    PARIS_IP,
    USA_MCC,
    FREMONT_LAT,
    FREMONT_LON,
    FREMONT_IP,
)
from ichnaea.service.geolocate.tests import \
    TestGeolocate as GeolocateRegressionTest


class TestGeoSubmit(CeleryAppTestCase):

    def setUp(self):
        CeleryAppTestCase.setUp(self)
        self.app.app.registry.db_slave = self.db_master

    def test_ok_cell(self):
        app = self.app
        session = self.db_master_session
        cell = Cell()
        cell.lat = from_degrees(PARIS_LAT + 0.1)
        cell.lon = from_degrees(PARIS_LON + 0.1)
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

    def test_ok_no_existing_cell(self):
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
                            status=200)

        self.assertEqual(res.content_type, 'application/json')
        self.assertEqual(res.json, {"location": {"lat": PARIS_LAT,
                                                 "lng": PARIS_LON},
                                    "accuracy": 12.4})

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
                "latitude": 12.3456700,
                "longitude": 23.4567800,
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
        self.assertEqual(res.json, {"location": {"lat": 12.3456700,
                                                 "lng": 23.4567800},
                                    "accuracy": 12.4})

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
                "latitude": 12.3456700,
                "longitude": 23.4567800,
                "accuracy": 12.4,
                "radioType": "gsm",
                "wifiAccessPoints": [
                    {"macAddress": "0000000000e5"},
                ]},
            status=200)

        self.assertEqual(res.content_type, 'application/json')
        self.assertEqual(res.json, {"location": {"lat": 12.3456700,
                                                 "lng": 23.4567800},
                                    "accuracy": 12.4})

        # Check that e5 exists
        query = session.query(Wifi)
        count = query.filter(Wifi.key == "0000000000e5").count()
        self.assertEquals(1, count)

        # check that WifiMeasure records are created
        self.assertEquals(1, session.query(WifiMeasure).count())

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

    def test_geoip_mismatch(self):
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
                            extra_environ={'HTTP_X_FORWARDED_FOR': FREMONT_IP},
                            status=200)

        self.assertEqual(res.content_type, 'application/json')
        self.assertEqual(res.json, {"location": {"lat": PARIS_LAT,
                                                 "lng": PARIS_LON},
                                    "accuracy": 12.4})

        # Check that no cell / cellmeasure were created
        self.assertEquals(0, session.query(Cell).count())
        self.assertEquals(0, session.query(CellMeasure).count())



class TestGeoSubmitBatch(CeleryAppTestCase):

    def setUp(self):
        CeleryAppTestCase.setUp(self)
        self.app.app.registry.db_slave = self.db_master

    def test_ok_cell(self):
        app = self.app
        session = self.db_master_session
        cell = Cell()
        cell.lat = from_degrees(PARIS_LAT)
        cell.lon = from_degrees(PARIS_LON)
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

    def test_geoip_match(self):
        app = self.app
        session = self.db_master_session
        cell = Cell()
        cell.lat = from_degrees(PARIS_LAT)
        cell.lon = from_degrees(PARIS_LON)
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

    def test_geoip_mismatch(self):
        app = self.app
        session = self.db_master_session
        cell = Cell()
        cell.lat = from_degrees(PARIS_LAT)
        cell.lon = from_degrees(PARIS_LON)
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
                                       {"latitude": FREMONT_LAT - 0.1,
                                        "longitude": FREMONT_LON - 0.1,
                                        "accuracy": 22.4,
                                        "radioType": "gsm",
                                        "cellTowers": [{
                                            "cellId": 2234,
                                            "locationAreaCode": 22,
                                            "mobileCountryCode": USA_MCC,
                                            "mobileNetworkCode": 2,
                                        }]}]},
                            extra_environ={'HTTP_X_FORWARDED_FOR': FREMONT_IP},
                            status=200)

        # check that we get an empty response
        self.assertEqual(res.content_type, 'application/json')
        self.assertEqual(res.json, {})

        # check that one new CellMeasure records is created
        self.assertEquals(1, session.query(CellMeasure).count())
        cm1 = session.query(CellMeasure).filter(
            CellMeasure.cid == 1234).count()
        cm2 = session.query(CellMeasure).filter(
            CellMeasure.cid == 2234).count()
        self.assertEquals(0, cm1)
        self.assertEquals(1, cm2)


class TestGeolocateRegression(GeolocateRegressionTest, CeleryAppTestCase):

    def setUp(self):
        CeleryAppTestCase.setUp(self)
        self.app.app.registry.db_slave = self.db_master

        self.url = '/v1/geosubmit'
        self.metric = 'geosubmit'

    def get_session(self):
        return self.db_master_session
