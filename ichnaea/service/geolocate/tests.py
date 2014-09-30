from sqlalchemy import text

from ichnaea.models import (
    Cell,
    Wifi,
    CELL_MIN_ACCURACY,
    CELLID_LAC,
    GEOIP_CITY_ACCURACY,
    RADIO_TYPE,
)
from ichnaea.heka_logging import RAVEN_ERROR
from ichnaea.tests.base import (
    AppTestCase,
    FRANCE_MCC,
    FREMONT_IP,
    FREMONT_LAT,
    FREMONT_LON,
    PARIS_LAT,
    PARIS_LON,
)


class TestGeolocate(AppTestCase):

    def setUp(self):
        AppTestCase.setUp(self)
        self.url = '/v1/geolocate'
        self.metric = 'geolocate'
        self.metric_url = 'request.v1.geolocate'

    def get_session(self):
        return self.db_slave_session

    def test_ok_cell(self):
        app = self.app
        session = self.get_session()
        cell = Cell()
        cell.lat = PARIS_LAT
        cell.lon = PARIS_LON
        cell.radio = RADIO_TYPE['gsm']
        cell.mcc = FRANCE_MCC
        cell.mnc = 1
        cell.lac = 2
        cell.cid = 1234
        session.add(cell)
        session.commit()

        res = app.post_json(
            '%s?key=test' % self.url, {
                "radioType": "gsm",
                "cellTowers": [
                    {"mobileCountryCode": FRANCE_MCC,
                     "mobileNetworkCode": 1,
                     "locationAreaCode": 2,
                     "cellId": 1234},
                ]},
            status=200)

        self.check_stats(
            counter=[self.metric_url + '.200', self.metric + '.api_key.test']
        )

        self.assertEqual(res.content_type, 'application/json')
        self.assertEqual(res.json, {"location": {"lat": PARIS_LAT,
                                                 "lng": PARIS_LON},
                                    "accuracy": CELL_MIN_ACCURACY})

    def test_ok_wifi(self):
        app = self.app
        session = self.get_session()
        wifis = [
            Wifi(key="a1", lat=1.0, lon=1.0),
            Wifi(key="b2", lat=1.001, lon=1.002),
            Wifi(key="c3", lat=1.002, lon=1.004),
            Wifi(key="d4", lat=None, lon=None),
        ]
        session.add_all(wifis)
        session.commit()
        res = app.post_json(
            '%s?key=test' % self.url, {
                "wifiAccessPoints": [
                    {"macAddress": "a1"},
                    {"macAddress": "b2"},
                    {"macAddress": "c3"},
                    {"macAddress": "d4"},
                ]},
            status=200)
        self.check_stats(
            counter=[self.metric + '.api_key.test'])
        self.assertEqual(res.content_type, 'application/json')
        self.assertEqual(res.json, {"location": {"lat": 1.001,
                                                 "lng": 1.002},
                                    "accuracy": 248.6090897})

    def test_wifi_not_found(self):
        app = self.app
        res = app.post_json(
            '%s?key=test' % self.url, {
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
        self.check_stats(
            counter=[self.metric + '.api_key.test',
                     self.metric_url + '.404'],
            timer=[self.metric_url],
        )
        self.check_expected_heka_messages(
            sentry=[('msg', RAVEN_ERROR, 0)]
        )

    def test_cell_mcc_mnc_strings(self):
        # mcc and mnc are officially defined as strings, where "01" is
        # different from "1". In practice many systems ours included treat
        # them as integers, so both of these are encoded as 1 instead.
        # Some clients sends us these values as strings, some as integers,
        # so we want to make sure we support both.
        app = self.app
        session = self.get_session()
        cell = Cell(
            lat=PARIS_LAT, lon=PARIS_LON,
            radio=RADIO_TYPE['gsm'], mcc=FRANCE_MCC, mnc=1, lac=2, cid=3)
        session.add(cell)
        session.commit()

        res = app.post_json(
            '%s?key=test' % self.url, {
                "radioType": "gsm",
                "cellTowers": [
                    {"mobileCountryCode": str(FRANCE_MCC),
                     "mobileNetworkCode": "01",
                     "locationAreaCode": 2,
                     "cellId": 3},
                ]},
            status=200)

        self.assertEqual(res.content_type, 'application/json')
        self.assertEqual(res.json, {"location": {"lat": PARIS_LAT,
                                                 "lng": PARIS_LON},
                                    "accuracy": CELL_MIN_ACCURACY})

    def test_geoip_fallback(self):
        app = self.app
        res = app.post_json(
            '%s?key=test' % self.url,
            {"wifiAccessPoints": [
                {"macAddress": "Porky"}, {"macAddress": "Piggy"},
                {"macAddress": "Davis"}, {"macAddress": "McSnappy"},
            ]},
            extra_environ={'HTTP_X_FORWARDED_FOR': FREMONT_IP},
            status=200)
        self.assertEqual(res.content_type, 'application/json')
        self.assertEqual(res.json, {"location": {"lat": 37.5079,
                                                 "lng": -121.96},
                                    "accuracy": GEOIP_CITY_ACCURACY})

    def test_empty_request_means_geoip(self):
        app = self.app
        res = app.post_json(
            '%s?key=test' % self.url, {},
            extra_environ={'HTTP_X_FORWARDED_FOR': FREMONT_IP},
            status=200)
        self.assertEqual(res.content_type, 'application/json')
        self.assertEqual(res.json, {"location": {"lat": 37.5079,
                                                 "lng": -121.96},
                                    "accuracy": GEOIP_CITY_ACCURACY})

    def test_parse_error(self):
        app = self.app
        res = app.post_json(
            '%s?key=test' % self.url, {
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

        self.check_stats(
            counter=[self.metric + '.api_key.test']
        )

    def test_no_data(self):
        app = self.app
        res = app.post_json(
            '%s?key=test' % self.url, {"wifiAccessPoints": []},
            status=400)
        self.assertEqual(res.content_type, 'application/json')

    def test_no_api_key(self):
        app = self.app
        session = self.get_session()
        key = dict(mcc=FRANCE_MCC, mnc=2, lac=3, cid=4)
        session.add(Cell(
            lat=PARIS_LAT,
            lon=PARIS_LON,
            radio=RADIO_TYPE['gsm'], **key)
        )
        session.commit()

        res = app.post_json(
            self.url, {
                "radioType": "gsm",
                "cellTowers": [
                    {"mobileCountryCode": FRANCE_MCC,
                     "mobileNetworkCode": 2,
                     "locationAreaCode": 3,
                     "cellId": 4},
                ]
            },
            status=400)
        self.assertEqual(res.content_type, 'application/json')
        self.assertEqual(u'Invalid API key', res.json['error']['message'])

        self.check_stats(
            counter=[self.metric + '.no_api_key'])

    def test_unknown_api_key(self):
        app = self.app
        session = self.get_session()
        key = dict(mcc=FRANCE_MCC, mnc=2, lac=3, cid=4)
        session.add(Cell(
            lat=PARIS_LAT,
            lon=PARIS_LON,
            radio=RADIO_TYPE['gsm'], **key)
        )
        session.commit()

        res = app.post_json(
            '%s?key=unknown_key' % self.url, {
                "radioType": "gsm",
                "cellTowers": [
                    {"mobileCountryCode": FRANCE_MCC,
                     "mobileNetworkCode": 2,
                     "locationAreaCode": 3,
                     "cellId": 4},
                ]
            },
            status=400)
        self.assertEqual(res.content_type, 'application/json')
        self.assertEqual(u'Invalid API key', res.json['error']['message'])

        self.check_stats(
            counter=[self.metric + '.unknown_api_key'])

    def test_lte_radio(self):
        app = self.app
        session = self.get_session()
        cells = [
            Cell(lat=PARIS_LAT,
                 lon=PARIS_LON,
                 radio=RADIO_TYPE['lte'],
                 mcc=FRANCE_MCC, mnc=1, lac=2, cid=3,
                 range=10000),
            Cell(lat=PARIS_LAT + 0.002,
                 lon=PARIS_LON + 0.004,
                 radio=RADIO_TYPE['lte'],
                 mcc=FRANCE_MCC, mnc=1, lac=2, cid=4,
                 range=20000),
        ]
        session.add_all(cells)
        session.commit()

        res = app.post_json(
            '%s?key=test' % self.url, {
                "radioType": "lte",
                "cellTowers": [
                    {"radio": "lte",
                     "mobileCountryCode": FRANCE_MCC,
                     "mobileNetworkCode": 1,
                     "locationAreaCode": 2,
                     "cellId": 3},
                    {"radio": "lte",
                     "mobileCountryCode": FRANCE_MCC,
                     "mobileNetworkCode": 1,
                     "locationAreaCode": 2,
                     "cellId": 4},
                ]},
            status=200)

        self.check_stats(
            counter=[self.metric_url + '.200', self.metric + '.api_key.test']
        )

        self.assertEqual(res.content_type, 'application/json')
        location = res.json['location']
        self.assertAlmostEquals(location['lat'], PARIS_LAT + 0.001)
        self.assertAlmostEquals(location['lng'], PARIS_LON + 0.002)
        self.assertEqual(res.json['accuracy'], CELL_MIN_ACCURACY)


class TestGeolocateFxOSWorkarounds(TestGeolocate):

    def test_ok_cell_radio_in_celltowers(self):
        # This test covers a bug related to FxOS calling the
        # geolocate API incorrectly.
        app = self.app
        session = self.get_session()
        cell = Cell()
        cell.lat = PARIS_LAT
        cell.lon = PARIS_LON
        cell.radio = 0
        cell.mcc = FRANCE_MCC
        cell.mnc = 1
        cell.lac = 2
        cell.cid = 1234
        session.add(cell)
        session.commit()

        res = app.post_json(
            '%s?key=test' % self.url, {
                "cellTowers": [
                    {"radio": "gsm",
                     "mobileCountryCode": FRANCE_MCC,
                     "mobileNetworkCode": 1,
                     "locationAreaCode": 2,
                     "cellId": 1234},
                ]},
            status=200)

        self.check_stats(
            counter=[self.metric_url + '.200', self.metric + '.api_key.test']
        )

        self.assertEqual(res.content_type, 'application/json')
        self.assertEqual(res.json, {"location": {"lat": PARIS_LAT,
                                                 "lng": PARIS_LON},
                                    "accuracy": CELL_MIN_ACCURACY})

    def test_ok_cell_radio_in_celltowers_dupes(self):
        # This test covered a bug related to FxOS calling the
        # geolocate API incorrectly.
        app = self.app
        session = self.get_session()
        cell = Cell()
        cell.lat = PARIS_LAT
        cell.lon = PARIS_LON
        cell.radio = 0
        cell.mcc = FRANCE_MCC
        cell.mnc = 1
        cell.lac = 2
        cell.cid = 1234
        session.add(cell)
        session.commit()
        res = app.post_json(
            '%s?key=test' % self.url, {
                "cellTowers": [
                    {"radio": "gsm",
                     "mobileCountryCode": FRANCE_MCC,
                     "mobileNetworkCode": 1,
                     "locationAreaCode": 2,
                     "cellId": 1234},
                    {"radio": "gsm",
                     "mobileCountryCode": FRANCE_MCC,
                     "mobileNetworkCode": 1,
                     "locationAreaCode": 2,
                     "cellId": 1234},
                ]},
            status=200)
        self.assertEqual(res.content_type, 'application/json')
        self.assertEqual(res.json, {"location": {"lat": PARIS_LAT,
                                                 "lng": PARIS_LON},
                                    "accuracy": CELL_MIN_ACCURACY})

    def test_inconsistent_cell_radio_in_towers(self):
        app = self.app
        session = self.get_session()
        cells = [
            Cell(lat=PARIS_LAT,
                 lon=PARIS_LON,
                 radio=RADIO_TYPE['gsm'],
                 mcc=FRANCE_MCC, mnc=1, lac=2, cid=3,
                 range=10000),
            Cell(lat=PARIS_LAT,
                 lon=PARIS_LON,
                 radio=RADIO_TYPE['gsm'],
                 mcc=FRANCE_MCC, mnc=1, lac=2, cid=CELLID_LAC,
                 range=20000),
            Cell(lat=PARIS_LAT + 0.002,
                 lon=PARIS_LON + 0.004,
                 radio=RADIO_TYPE['umts'],
                 mcc=FRANCE_MCC, mnc=2, lac=3, cid=4,
                 range=2000),
            Cell(lat=PARIS_LAT + 0.002,
                 lon=PARIS_LON + 0.004,
                 radio=RADIO_TYPE['umts'],
                 mcc=FRANCE_MCC, mnc=2, lac=3, cid=CELLID_LAC,
                 range=15000),
        ]
        session.add_all(cells)
        session.commit()

        res = app.post_json(
            '%s?key=test' % self.url, {
                "radioType": "cdma",
                "cellTowers": [
                    {"radio": "gsm",
                     "mobileCountryCode": FRANCE_MCC,
                     "mobileNetworkCode": 1,
                     "locationAreaCode": 2,
                     "cellId": 3},
                    {"radio": "wcdma",
                     "mobileCountryCode": FRANCE_MCC,
                     "mobileNetworkCode": 2,
                     "locationAreaCode": 3,
                     "cellId": 4},
                ]},
            status=200)

        self.check_stats(
            counter=[self.metric_url + '.200', self.metric + '.api_key.test']
        )

        self.assertEqual(res.content_type, 'application/json')
        location = res.json['location']
        self.assertAlmostEquals(location['lat'], PARIS_LAT + 0.002)
        self.assertAlmostEquals(location['lng'], PARIS_LON + 0.004)
        self.assertEqual(res.json['accuracy'], CELL_MIN_ACCURACY)


class TestGeolocateErrors(AppTestCase):
    # this is a standalone class to ensure DB isolation for dropping tables

    def tearDown(self):
        self.setup_tables(self.db_master.engine)
        super(TestGeolocateErrors, self).tearDown()

    def test_database_error(self):
        app = self.app
        session = self.db_slave_session
        stmt = text("drop table wifi;")
        session.execute(stmt)
        stmt = text("drop table cell;")
        session.execute(stmt)

        res = app.post_json(
            '/v1/geolocate?key=test', {
                "radioType": "gsm",
                "cellTowers": [
                    {"mobileCountryCode": FRANCE_MCC,
                     "mobileNetworkCode": 1,
                     "locationAreaCode": 2,
                     "cellId": 1234},
                ],
                "wifiAccessPoints": [
                    {"macAddress": "a1"},
                    {"macAddress": "b2"},
                ]},
            extra_environ={'HTTP_X_FORWARDED_FOR': FREMONT_IP},
            status=200)

        self.assertEqual(res.content_type, 'application/json')
        self.assertEqual(res.json, {"location": {"lat": FREMONT_LAT,
                                                 "lng": FREMONT_LON},
                                    "accuracy": GEOIP_CITY_ACCURACY})

        self.check_stats(
            timer=['request.v1.geolocate'],
            counter=[
                'request.v1.geolocate.200',
                'geolocate.geoip_hit',
                'geolocate.no_wifi_found',
                'geolocate.wifi_error',
            ],
        )
        self.check_expected_heka_messages(
            sentry=[('msg', RAVEN_ERROR, 2)]
        )
