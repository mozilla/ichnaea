from sqlalchemy import text
from webob.response import gzip_app_iter

from ichnaea.constants import CELL_MIN_ACCURACY
from ichnaea.customjson import dumps, loads
from ichnaea.logging import RAVEN_ERROR
from ichnaea.models import (
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

from ichnaea.service.base import INVALID_API_KEY


class TestSearch(AppTestCase):

    def test_ok_cell(self):
        app = self.app
        session = self.db_slave_session
        key = dict(mcc=FRANCE_MCC, mnc=2, lac=3)
        lat = PARIS_LAT
        lon = PARIS_LON
        data = [
            Cell(lat=lat, lon=lon, radio=2, cid=4, **key),
            Cell(lat=lat + 0.002, lon=lon + 0.004, radio=2, cid=5, **key),
        ]
        session.add_all(data)
        session.commit()

        res = app.post_json(
            '/v1/search?key=test',
            {"radio": "gsm", "cell": [
                dict(radio="umts", cid=4, **key),
                dict(radio="umts", cid=5, **key),
            ]},
            status=200)

        self.assertEqual(res.content_type, 'application/json')
        self.assertEqual(res.json, {"status": "ok",
                                    "lat": PARIS_LAT + 0.001,
                                    "lon": PARIS_LON + 0.002,
                                    "accuracy": CELL_MIN_ACCURACY})

        self.check_stats(
            total=10,
            timer=[('request.v1.search', 1),
                   ('search.accuracy.cell', 1)],
            counter=[('search.api_key.test', 1),
                     ('search.cell_hit', 1),
                     ('request.v1.search.200', 1),
                     ('search.cell_found', 1),
                     ('search.no_cell_lac_found', 1),
                     ('search.no_geoip_found', 1),
                     ('search.country_from_mcc', 1),
                     ('search.api_log.test.cell_hit', 1)]
        )

    def test_ok_wifi(self):
        app = self.app
        session = self.db_slave_session
        wifis = [
            Wifi(key="101010101010", lat=1.0, lon=1.0),
            Wifi(key="202020202020", lat=1.002, lon=1.004),
            Wifi(key="303030303030", lat=None, lon=None),
        ]
        session.add_all(wifis)
        session.commit()
        res = app.post_json('/v1/search?key=test',
                            {"wifi": [
                                {"key": "101010101010"},
                                {"key": "202020202020"},
                                {"key": "303030303030"},
                            ]},
                            status=200)
        self.assertEqual(res.content_type, 'application/json')
        self.assertEqual(res.json, {"status": "ok",
                                    "lat": 1.001, "lon": 1.002,
                                    "accuracy": 248.6090897})

        self.check_stats(
            timer=[('request.v1.search', 1),
                   ('search.accuracy.wifi', 1)],
            counter=[('search.api_key.test', 1),
                     ('search.wifi_hit', 1),
                     ('request.v1.search.200', 1),
                     ('search.wifi_found', 1),
                     ('search.no_geoip_found', 1),
                     ('search.no_country', 1),
                     ('search.api_log.test.wifi_hit', 1)]
        )

    def test_not_found(self):
        app = self.app
        res = app.post_json('/v1/search?key=test',
                            {"cell": [{"mcc": FRANCE_MCC, "mnc": 2,
                                       "lac": 3, "cid": 4}]},
                            status=200)
        self.assertEqual(res.content_type, 'application/json')
        self.assertEqual(res.json, {"status": "not_found"})

        self.check_stats(counter=['search.api_key.test',
                                  'search.miss'])

    def test_wifi_not_found(self):
        app = self.app
        res = app.post_json('/v1/search?key=test', {"wifi": [
                            {"key": "101010101010"},
                            {"key": "202020202020"}]},
                            status=200)
        self.assertEqual(res.content_type, 'application/json')
        self.assertEqual(res.json, {"status": "not_found"})

        self.check_stats(counter=['search.api_key.test',
                                  'search.miss',
                                  'search.api_log.test.wifi_miss'])

    def test_geoip_fallback(self):
        app = self.app
        london = self.geoip_data['London']
        res = app.post_json(
            '/v1/search?key=test',
            {"wifi": [
                {"key": "a0fffffff0ff"}, {"key": "b1ffff0fffff"},
                {"key": "c2fffffffff0"}, {"key": "d3fffff0ffff"},
            ]},
            extra_environ={'HTTP_X_FORWARDED_FOR': london['ip']},
            status=200)
        self.assertEqual(res.content_type, 'application/json')
        self.assertEqual(res.json, {"status": "ok",
                                    "lat": london['latitude'],
                                    "lon": london['longitude'],
                                    "accuracy": london['accuracy']})

        self.check_stats(
            timer=[('request.v1.search', 1),
                   ('search.accuracy.geoip', 1)],
            counter=[('search.api_key.test', 1),
                     ('search.geoip_hit', 1),
                     ('request.v1.search.200', 1),
                     ('search.no_wifi_found', 1),
                     ('search.geoip_city_found', 1),
                     ('search.country_from_geoip', 1),
                     ('search.api_log.test.wifi_miss', 1)]
        )

    def test_empty_request_means_geoip(self):
        app = self.app
        london = self.geoip_data['London']
        res = app.post_json(
            '/v1/search?key=test', {},
            extra_environ={'HTTP_X_FORWARDED_FOR': london['ip']},
            status=200)
        self.assertEqual(res.content_type, 'application/json')
        self.assertEqual(res.json, {"status": "ok",
                                    "lat": london['latitude'],
                                    "lon": london['longitude'],
                                    "accuracy": london['accuracy']})

        self.check_stats(
            total=8,
            timer=[('request.v1.search', 1),
                   ('search.accuracy.geoip', 1)],
            counter=[('search.api_key.test', 1),
                     ('search.geoip_hit', 1),
                     ('request.v1.search.200', 1),
                     ('search.geoip_city_found', 1),
                     ('search.country_from_geoip', 1),
                     ('search.api_log.test.geoip_hit', 1)]
        )

    def test_error(self):
        app = self.app
        res = app.post_json('/v1/search?key=test', {"cell": 1}, status=400)
        self.assertEqual(res.content_type, 'application/json')
        self.assertTrue('errors' in res.json)
        self.assertFalse('status' in res.json)

    def test_error_unknown_key(self):
        app = self.app
        res = app.post_json('/v1/search?key=test', {"foo": 0}, status=200)
        self.assertEqual(res.content_type, 'application/json')
        self.assertEqual(res.json, {"status": "not_found"})

    def test_error_no_mapping(self):
        app = self.app
        res = app.post_json('/v1/search?key=test', [1], status=200)
        self.assertEqual(res.content_type, 'application/json')
        self.assertEqual(res.json, {"status": "not_found"})

    def test_no_valid_keys(self):
        app = self.app
        res = app.post_json('/v1/search?key=test', {"wifi": [
                            {"key": ":"}, {"key": ".-"}]},
                            status=200)
        self.assertEqual(res.json, {"status": "not_found"})

    def test_no_json(self):
        app = self.app
        res = app.post('/v1/search?key=test', "\xae", status=400)
        self.assertTrue('errors' in res.json)
        self.check_stats(counter=['search.api_key.test'])

    def test_gzip(self):
        app = self.app
        data = {"cell": [{"mcc": FRANCE_MCC, "mnc": 2, "lac": 3, "cid": 4}]}
        body = ''.join(gzip_app_iter(dumps(data)))
        headers = {
            'Content-Encoding': 'gzip',
        }
        res = app.post('/v1/search?key=test', body, headers=headers,
                       content_type='application/json', status=200)
        self.assertEqual(res.content_type, 'application/json')
        self.assertEqual(res.json, {"status": "not_found"})

    def test_no_api_key(self):
        app = self.app
        session = self.db_slave_session
        key = dict(mcc=FRANCE_MCC, mnc=2, lac=3, cid=4)
        session.add(Cell(
            lat=PARIS_LAT,
            lon=PARIS_LON,
            radio=RADIO_TYPE['umts'], **key)
        )
        session.commit()

        res = app.post_json(
            '/v1/search',
            {"radio": "gsm", "cell": [
                dict(radio="umts", **key),
            ]},
            status=400)
        self.assertEqual(res.json, loads(INVALID_API_KEY))
        self.check_stats(counter=['search.no_api_key'])

    def test_unknown_api_key(self):
        app = self.app
        session = self.db_slave_session
        key = dict(mcc=FRANCE_MCC, mnc=2, lac=3, cid=4)
        session.add(Cell(
            lat=PARIS_LAT,
            lon=PARIS_LON,
            radio=RADIO_TYPE['umts'], **key)
        )
        session.commit()

        res = app.post_json(
            '/v1/search?key=unknown_key',
            {"radio": "gsm", "cell": [
                dict(radio="umts", **key),
            ]},
            status=400)
        self.assertEqual(res.json, loads(INVALID_API_KEY))
        self.check_stats(counter=['search.unknown_api_key'])


class TestSearchErrors(AppTestCase):
    # this is a standalone class to ensure DB isolation for dropping tables

    def tearDown(self):
        self.setup_tables(self.db_master.engine)
        super(TestSearchErrors, self).tearDown()

    def test_database_error(self):
        app = self.app
        london = self.geoip_data['London']
        session = self.db_slave_session
        stmt = text("drop table wifi;")
        session.execute(stmt)

        res = app.post_json(
            '/v1/search?key=test',
            {"wifi": [
                {"key": "101010101010"},
                {"key": "202020202020"},
                {"key": "303030303030"},
                {"key": "404040404040"},
            ]},
            extra_environ={'HTTP_X_FORWARDED_FOR': london['ip']},
        )

        self.assertEqual(res.json, {"status": "ok",
                                    "lat": london['latitude'],
                                    "lon": london['longitude'],
                                    "accuracy": london['accuracy']})

        self.check_stats(
            timer=['request.v1.search'],
            counter=[
                'request.v1.search.200',
                'search.geoip_hit',
                'search.no_wifi_found',
                'search.wifi_error',
            ],
        )
        self.check_expected_heka_messages(
            sentry=[('msg', RAVEN_ERROR, 1)]
        )
