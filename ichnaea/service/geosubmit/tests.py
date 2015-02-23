import time

from ichnaea.models import (
    Cell,
    CellObservation,
    Radio,
    User,
    Wifi,
    WifiObservation,
)
from ichnaea.tests.base import (
    CeleryAppTestCase,
    GB_LAT,
    GB_LON,
    GB_MCC,
)
from ichnaea.util import utcnow


class TestGeoSubmit(CeleryAppTestCase):

    def test_ok_cell(self):
        app = self.app
        session = self.db_master_session
        cell = Cell()
        cell.lat = GB_LAT
        cell.lon = GB_LON
        cell.radio = Radio.cdma
        cell.mcc = GB_MCC
        cell.mnc = 1
        cell.lac = 2
        cell.cid = 1234
        cell.range = 10000
        cell.total_measures = 1
        cell.new_measures = 0

        session.add(cell)
        session.commit()

        res = app.post_json(
            '/v1/geosubmit?key=test',
            {"items": [
                {"latitude": GB_LAT + 0.1,
                 "longitude": GB_LON + 0.1,
                 "accuracy": 12.4,
                 "radioType": Radio.cdma.name,
                 "cellTowers": [{
                     "cellId": 1234,
                     "locationAreaCode": 2,
                     "mobileCountryCode": GB_MCC,
                     "mobileNetworkCode": 1,
                 }]},
                {"latitude": GB_LAT - 0.1,
                 "longitude": GB_LON - 0.1,
                 "accuracy": 22.4,
                 "cellTowers": [{
                     "radioType": "wcdma",
                     "cellId": 2234,
                     "locationAreaCode": 22,
                     "mobileCountryCode": GB_MCC,
                     "mobileNetworkCode": 2,
                 }]},
            ]},
            status=200)

        # check that we get an empty response
        self.assertEqual(res.content_type, 'application/json')
        self.assertEqual(res.json, {})

        self.assertEqual(session.query(Cell).count(), 2)

        observations = session.query(CellObservation).all()
        self.assertEqual(len(observations), 2)
        radios = set([obs.radio for obs in observations])
        self.assertEqual(radios, set([Radio.cdma, Radio.umts]))

        self.check_stats(
            counter=['geosubmit.api_key.test',
                     'items.api_log.test.uploaded.batches',
                     'items.api_log.test.uploaded.reports',
                     'items.api_log.test.uploaded.cell_observations',
                     'items.uploaded.cell_observations',
                     'items.uploaded.batches',
                     'items.uploaded.reports',
                     'request.v1.geosubmit.200',
                     ],
            timer=['items.api_log.test.uploaded.batch_size',
                   'items.uploaded.batch_size',
                   'request.v1.geosubmit'])

    def test_ok_no_existing_cell(self):
        app = self.app
        session = self.db_master_session
        now_ms = int(time.time() * 1000)
        first_of_month = utcnow().replace(day=1, hour=0, minute=0, second=0)

        res = app.post_json(
            '/v1/geosubmit?key=test',
            {"items": [
                {"latitude": GB_LAT,
                 "longitude": GB_LON,
                 "accuracy": 12.4,
                 "altitude": 100.1,
                 "altitudeAccuracy": 23.7,
                 "heading": 45.0,
                 "speed": 3.6,
                 "timestamp": now_ms,
                 "radioType": Radio.gsm.name,
                 "cellTowers": [{
                     "radioType": Radio.lte.name,
                     "cellId": 1234,
                     "locationAreaCode": 2,
                     "mobileCountryCode": GB_MCC,
                     "mobileNetworkCode": 1,
                     "age": 3,
                     "asu": 31,
                     "psc": 15,
                     "signalStrength": -51,
                     "timingAdvance": 1,
                 }]},
            ]},
            status=200)

        self.assertEqual(res.content_type, 'application/json')
        self.assertEqual(res.json, {})

        self.assertEquals(session.query(Cell).count(), 1)

        # check that one new observation was created
        result = session.query(CellObservation).all()
        self.assertEquals(len(result), 1)
        obs = result[0]
        self.assertEqual(obs.lat, GB_LAT)
        self.assertEqual(obs.lon, GB_LON)
        self.assertEqual(obs.accuracy, 12)
        self.assertEqual(obs.altitude, 100)
        self.assertEqual(obs.altitude_accuracy, 24)
        self.assertEqual(obs.heading, 45.0)
        self.assertEqual(obs.speed, 3.6)
        self.assertEqual(obs.time, first_of_month)
        self.assertEqual(obs.radio, Radio.lte)
        self.assertEqual(obs.mcc, GB_MCC)
        self.assertEqual(obs.mnc, 1)
        self.assertEqual(obs.lac, 2)
        self.assertEqual(obs.cid, 1234)
        self.assertEqual(obs.psc, 15)
        self.assertEqual(obs.asu, 31)
        self.assertEqual(obs.signal, -51)
        self.assertEqual(obs.ta, 1)

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
            '/v1/geosubmit?key=test',
            {"items": [
                {"latitude": 12.34567,
                 "longitude": 23.45678,
                 "accuracy": 12.4,
                 "radioType": Radio.gsm.name,
                 "wifiAccessPoints": [
                     {"macAddress": "101010101010"},
                     {"macAddress": "202020202020"},
                     {"macAddress": "303030303030"},
                     {"macAddress": "404040404040"},
                     {"macAddress": "505050505050"},
                 ]},
            ]},
            status=200)

        self.assertEqual(res.content_type, 'application/json')
        self.assertEqual(res.json, {})

        # Check that 505050505050 exists
        query = session.query(Wifi)
        count = query.filter(Wifi.key == "505050505050").count()
        self.assertEquals(1, count)

        # check that WifiObservation records are created
        self.assertEquals(5, session.query(WifiObservation).count())

        self.check_stats(
            counter=['items.api_log.test.uploaded.batches',
                     'items.api_log.test.uploaded.reports',
                     'items.api_log.test.uploaded.wifi_observations',
                     'items.uploaded.wifi_observations',
                     ],
            timer=['items.api_log.test.uploaded.batch_size'])

    def test_ok_no_existing_wifi(self):
        app = self.app
        session = self.db_master_session

        res = app.post_json(
            '/v1/geosubmit?key=test',
            {"items": [
                {"latitude": GB_LAT,
                 "longitude": GB_LON,
                 "accuracy": 12.4,
                 "radioType": Radio.gsm.name,
                 "wifiAccessPoints": [{
                     "macAddress": "505050505050",
                     "age": 3,
                     "channel": 6,
                     "frequency": 2437,
                     "signalToNoiseRatio": 13,
                     "signalStrength": -77,
                 }]},
            ]},
            status=200)

        self.assertEqual(res.content_type, 'application/json')
        self.assertEqual(res.json, {})

        # Check that 505050505050 exists
        query = session.query(Wifi)
        count = query.filter(Wifi.key == "505050505050").count()
        self.assertEquals(count, 1)

        # check that WifiObservation records are created
        result = session.query(WifiObservation).all()
        self.assertEquals(len(result), 1)
        obs = result[0]
        self.assertEqual(obs.lat, GB_LAT)
        self.assertEqual(obs.lon, GB_LON)
        self.assertEqual(obs.channel, 6)
        self.assertEqual(obs.signal, -77)
        self.assertEqual(obs.snr, 13)

    def test_invalid_json(self):
        session = self.db_master_session
        self.app.post_json(
            '/v1/geosubmit?key=test',
            {"items": [
                {"latitude": GB_LAT,
                 "longitude": GB_LON,
                 "wifiAccessPoints": [{
                     "macAddress": 10,
                 }]},
            ]},
            status=400)
        self.assertEquals(session.query(WifiObservation).count(), 0)

    def test_invalid_latitude(self):
        session = self.db_master_session
        self.app.post_json(
            '/v1/geosubmit?key=test',
            {"items": [
                {"latitude": 12345.0,
                 "longitude": GB_LON,
                 "wifiAccessPoints": [{
                     "macAddress": "505050505050",
                 }]},
            ]},
            status=200)
        self.assertEquals(session.query(WifiObservation).count(), 0)

    def test_invalid_cell(self):
        session = self.db_master_session
        self.app.post_json(
            '/v1/geosubmit?key=test',
            {"items": [
                {"latitude": GB_LAT,
                 "longitude": GB_LON,
                 "cellTowers": [{
                     "radioType": Radio.gsm.name,
                     "cellId": 12,
                     "locationAreaCode": 34,
                     "mobileCountryCode": GB_MCC,
                     "mobileNetworkCode": 2000,
                 }]},
            ]},
            status=200)
        self.assertEquals(session.query(CellObservation).count(), 0)

    def test_duplicated_cell_observations(self):
        session = self.db_master_session
        self.app.post_json(
            '/v1/geosubmit?key=test',
            {"items": [
                {"latitude": GB_LAT,
                 "longitude": GB_LON,
                 "cellTowers": [
                     {"radioType": Radio.gsm.name,
                      "cellId": 12,
                      "locationAreaCode": 34,
                      "mobileCountryCode": GB_MCC,
                      "mobileNetworkCode": 5,
                      "asu": 10},
                     {"radioType": Radio.gsm.name,
                      "cellId": 12,
                      "locationAreaCode": 34,
                      "mobileCountryCode": GB_MCC,
                      "mobileNetworkCode": 5,
                      "asu": 16},
                 ]},
            ]},
            status=200)
        self.assertEquals(session.query(CellObservation).count(), 1)

    def test_duplicated_wifi_observations(self):
        session = self.db_master_session
        self.app.post_json(
            '/v1/geosubmit?key=test',
            {"items": [
                {"latitude": GB_LAT,
                 "longitude": GB_LON,
                 "wifiAccessPoints": [
                     {"macAddress": "101010101010",
                      "signalStrength": -92},
                     {"macAddress": "101010101010",
                      "signalStrength": -77},
                 ]},
            ]},
            status=200)
        self.assertEquals(session.query(WifiObservation).count(), 1)

    def test_email_header(self):
        nickname = 'World Tr\xc3\xa4veler'
        email = 'world_tr\xc3\xa4veler@email.com'
        session = self.db_master_session
        self.app.post_json(
            '/v1/geosubmit?key=test',
            {"items": [
                {"latitude": 12.34567,
                 "longitude": 23.45678,
                 "accuracy": 12.4,
                 "radioType": Radio.gsm.name,
                 "wifiAccessPoints": [
                     {"macAddress": "101010101010"},
                     {"macAddress": "202020202020"},
                     {"macAddress": "303030303030"},
                     {"macAddress": "404040404040"},
                     {"macAddress": "505050505050"},
                 ]},
            ]},
            headers={
                'X-Nickname': nickname,
                'X-Email': email,
            },
            status=200)

        session = self.db_master_session
        result = session.query(User).all()
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].email, email.decode('utf-8'))

    def test_batches(self):
        session = self.db_master_session
        EXPECTED_RECORDS = 110
        wifi_data = [{"macAddress": "101010101010"}]
        items = [{"latitude": GB_LAT,
                  "longitude": GB_LON + (i / 10000.0),
                  "wifiAccessPoints": wifi_data}
                 for i in range(EXPECTED_RECORDS)]

        # let's add a bad one, this will just be skipped
        items.append({'lat': 10, 'lon': 10, 'whatever': 'xx'})
        self.app.post_json('/v1/geosubmit?key=test',
                           {"items": items}, status=200)

        result = session.query(WifiObservation).all()
        self.assertEqual(len(result), EXPECTED_RECORDS)
