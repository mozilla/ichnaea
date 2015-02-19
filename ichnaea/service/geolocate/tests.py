from uuid import uuid1

from sqlalchemy import text

from ichnaea.constants import CELL_MIN_ACCURACY
from ichnaea.logging import RAVEN_ERROR
from ichnaea.models import (
    ApiKey,
    Cell,
    Wifi,
    RADIO_TYPE,
)
from ichnaea.tests.base import (
    AppTestCase,
    FRANCE_MCC,
    PARIS_LAT,
    PARIS_LON,
)
from ichnaea import util


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
            counter=[self.metric_url + '.200',
                     self.metric + '.api_key.test',
                     self.metric + '.api_log.test.cell_hit']
        )

        self.assertEqual(res.content_type, 'application/json')
        self.assertEqual(res.json, {"location": {"lat": PARIS_LAT,
                                                 "lng": PARIS_LON},
                                    "accuracy": CELL_MIN_ACCURACY})

    def test_ok_wifi(self):
        app = self.app
        session = self.get_session()
        wifis = [
            Wifi(key="101010101010", lat=1.0, lon=1.0),
            Wifi(key="202020202020", lat=1.001, lon=1.002),
            Wifi(key="303030303030", lat=1.002, lon=1.004),
            Wifi(key="404040404040", lat=None, lon=None),
        ]
        session.add_all(wifis)
        session.commit()
        res = app.post_json(
            '%s?key=test' % self.url, {
                "wifiAccessPoints": [
                    {"macAddress": "101010101010"},
                    {"macAddress": "202020202020"},
                    {"macAddress": "303030303030"},
                    {"macAddress": "404040404040"},
                ]},
            status=200)
        self.check_stats(
            counter=[self.metric + '.api_key.test',
                     self.metric + '.api_log.test.wifi_hit'])
        self.assertEqual(res.content_type, 'application/json')
        self.assertEqual(res.json, {"location": {"lat": 1.001,
                                                 "lng": 1.002},
                                    "accuracy": 248.6090897})

    def test_wifi_not_found(self):
        app = self.app
        res = app.post_json(
            '%s?key=test' % self.url, {
                "wifiAccessPoints": [
                    {"macAddress": "101010101010"},
                    {"macAddress": "202020202020"},
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
                     self.metric + '.api_log.test.wifi_miss',
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
        london = self.geoip_data['London']
        res = app.post_json(
            '%s?key=test' % self.url,
            {"wifiAccessPoints": [
                {"macAddress": "101010101010"},
                {"macAddress": "202020202020"},
                {"macAddress": "303030303030"},
                {"macAddress": "404040404040"},
            ]},
            extra_environ={'HTTP_X_FORWARDED_FOR': london['ip']},
            status=200)
        self.assertEqual(res.content_type, 'application/json')
        self.assertEqual(res.json, {"location": {"lat": london['latitude'],
                                                 "lng": london['longitude']},
                                    "accuracy": london['accuracy']})

    def test_empty_request_means_geoip(self):
        app = self.app
        london = self.geoip_data['London']
        res = app.post_json(
            '%s?key=test' % self.url, {},
            extra_environ={'HTTP_X_FORWARDED_FOR': london['ip']},
            status=200)
        self.assertEqual(res.content_type, 'application/json')
        self.assertEqual(res.json, {"location": {"lat": london['latitude'],
                                                 "lng": london['longitude']},
                                    "accuracy": london['accuracy']})

    def test_incomplete_request_means_geoip(self):
        app = self.app
        london = self.geoip_data['London']
        res = app.post_json(
            '%s?key=test' % self.url, {"wifiAccessPoints": []},
            extra_environ={'HTTP_X_FORWARDED_FOR': london['ip']},
            status=200)
        self.assertEqual(res.content_type, 'application/json')
        self.assertEqual(res.json, {"location": {"lat": london['latitude'],
                                                 "lng": london['longitude']},
                                    "accuracy": london['accuracy']})

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

    def test_api_key_limit(self):
        app = self.app
        london = self.geoip_data['London']
        session = self.get_session()
        api_key = uuid1().hex
        session.add(ApiKey(valid_key=api_key, maxreq=5, shortname='dis'))
        session.flush()

        # exhaust today's limit
        dstamp = util.utcnow().strftime("%Y%m%d")
        key = "apilimit:%s:%s" % (api_key, dstamp)
        self.redis_client.incr(key, 10)

        res = app.post_json(
            '%s?key=%s' % (self.url, api_key), {},
            extra_environ={'HTTP_X_FORWARDED_FOR': london['ip']},
            status=403)

        errors = res.json['error']['errors']
        self.assertEqual(errors[0]['reason'], 'dailyLimitExceeded')

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


class TestGeolocateFxOSWorkarounds(AppTestCase):

    def setUp(self):
        AppTestCase.setUp(self)
        self.url = '/v1/geolocate'
        self.metric = 'geolocate'
        self.metric_url = 'request.v1.geolocate'

    def get_session(self):
        return self.db_slave_session

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
            Cell(lat=PARIS_LAT + 0.002,
                 lon=PARIS_LON + 0.004,
                 radio=RADIO_TYPE['umts'],
                 mcc=FRANCE_MCC, mnc=2, lac=3, cid=4,
                 range=2000),
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
        london = self.geoip_data['London']
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
                    {"macAddress": "101010101010"},
                    {"macAddress": "202020202020"},
                ]},
            extra_environ={'HTTP_X_FORWARDED_FOR': london['ip']},
            status=200)

        self.assertEqual(res.content_type, 'application/json')
        self.assertEqual(res.json, {"location": {"lat": london['latitude'],
                                                 "lng": london['longitude']},
                                    "accuracy": london['accuracy']})

        self.check_stats(
            timer=['request.v1.geolocate'],
            counter=[
                'request.v1.geolocate.200',
                'geolocate.geoip_hit',
            ],
        )
        self.check_expected_heka_messages(
            sentry=[('msg', RAVEN_ERROR, 2)]
        )
