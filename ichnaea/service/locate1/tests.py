import requests_mock
from pyramid.testing import DummyRequest
from sqlalchemy import text

from ichnaea.constants import CELL_MIN_ACCURACY, LAC_MIN_ACCURACY
from ichnaea.customjson import dumps, loads
from ichnaea.models import (
    ApiKey,
    Cell,
    CellArea,
    Radio,
    Wifi,
)
from ichnaea.service.base import INVALID_API_KEY
from ichnaea.service.error import preprocess_request
from ichnaea.service.locate1.schema import Locate1Schema
from ichnaea.tests.base import (
    AppTestCase,
    FRANCE_MCC,
    PARIS_LAT,
    PARIS_LON,
    TestCase,
)
from ichnaea import util


class TestSchema(TestCase):

    def _make_schema(self):
        return Locate1Schema()

    def _make_request(self, body):
        request = DummyRequest()
        request.body = body
        return request

    def test_empty(self):
        schema = self._make_schema()
        request = self._make_request('{}')
        data, errors = preprocess_request(request, schema, None)
        self.assertEqual(errors, [])
        self.assertEqual(
            data, {'cell': (), 'wifi': (), 'radio': None, 'fallbacks': None})

    def test_empty_cell_entry(self):
        schema = self._make_schema()
        request = self._make_request('{"cell": [{}]}')
        data, errors = preprocess_request(request, schema, None)
        self.assertTrue('cell' in data)

    def test_wrong_cell_data(self):
        schema = self._make_schema()
        request = self._make_request(
            '{"cell": [{"mcc": "a", "mnc": 2, "lac": 3, "cid": 4}]}')
        data, errors = preprocess_request(request, schema, None)
        self.assertTrue(errors)


class TestView(AppTestCase):

    def test_ok_cell(self):
        app = self.app
        session = self.session
        key = dict(mcc=FRANCE_MCC, mnc=2, lac=3)
        lat = PARIS_LAT
        lon = PARIS_LON
        data = [
            Cell(lat=lat, lon=lon, range=1000,
                 radio=Radio.umts, cid=4, **key),
            Cell(lat=lat + 0.002, lon=lon + 0.004, range=1000,
                 radio=Radio.umts, cid=5, **key),
        ]
        session.add_all(data)
        session.commit()

        res = app.post_json(
            '/v1/search?key=test',
            {'radio': Radio.gsm.name, 'cell': [
                dict(radio=Radio.umts.name, cid=4, **key),
                dict(radio=Radio.umts.name, cid=5, **key),
            ]},
            status=200)

        self.assertEqual(res.content_type, 'application/json')
        self.assertEqual(res.json, {'status': 'ok',
                                    'lat': PARIS_LAT + 0.001,
                                    'lon': PARIS_LON + 0.002,
                                    'accuracy': CELL_MIN_ACCURACY})

        self.check_stats(
            timer=[('request.v1.search', 1)],
            counter=[('search.api_key.test', 1),
                     ('search.cell_hit', 1),
                     ('request.v1.search.200', 1),
                     ('search.api_log.test.cell_hit', 1)],
        )

    def test_ok_cellarea_when_fallback_not_set(self):
        app = self.app
        session = self.session
        key = dict(mcc=FRANCE_MCC, mnc=2, lac=3)
        lat = PARIS_LAT
        lon = PARIS_LON
        data = [
            CellArea(lat=lat, lon=lon, range=1000,
                     radio=Radio.umts, **key),
        ]
        session.add_all(data)
        session.commit()

        res = app.post_json(
            '/v1/search?key=test',
            {
                'radio': Radio.gsm.name,
                'cell': [
                    dict(radio=Radio.umts.name, **key),
                    dict(radio=Radio.umts.name, **key),
                ],
            },
            status=200)

        self.assertEqual(res.content_type, 'application/json')
        self.assertEqual(res.json, {'status': 'ok',
                                    'lat': PARIS_LAT,
                                    'lon': PARIS_LON,
                                    'accuracy': LAC_MIN_ACCURACY,
                                    'fallback': 'lacf'})

        self.check_stats(
            timer=[('request.v1.search', 1)],
            counter=[('search.api_key.test', 1),
                     ('search.cell_lac_hit', 1),
                     ('request.v1.search.200', 1),
                     ('search.api_log.test.cell_lac_hit', 1)],
        )

    def test_ok_cellarea_when_fallback_set(self):
        app = self.app
        session = self.session
        key = dict(mcc=FRANCE_MCC, mnc=2, lac=3)
        lat = PARIS_LAT
        lon = PARIS_LON
        data = [
            CellArea(lat=lat, lon=lon, range=1000,
                     radio=Radio.umts, **key),
        ]
        session.add_all(data)
        session.commit()

        res = app.post_json(
            '/v1/search?key=test',
            {
                'radio': Radio.gsm.name,
                'cell': [
                    dict(radio=Radio.umts.name, **key),
                    dict(radio=Radio.umts.name, **key),
                ],
                'fallbacks': {
                    'lacf': 1,
                },
            },
            status=200)

        self.assertEqual(res.content_type, 'application/json')
        self.assertEqual(res.json, {'status': 'ok',
                                    'lat': PARIS_LAT,
                                    'lon': PARIS_LON,
                                    'accuracy': LAC_MIN_ACCURACY,
                                    'fallback': 'lacf'})

        self.check_stats(
            timer=[('request.v1.search', 1)],
            counter=[('search.api_key.test', 1),
                     ('search.cell_lac_hit', 1),
                     ('request.v1.search.200', 1),
                     ('search.api_log.test.cell_lac_hit', 1)],
        )

    def test_ok_cellarea_when_different_fallback_set(self):
        app = self.app
        session = self.session
        key = dict(mcc=FRANCE_MCC, mnc=2, lac=3)
        lat = PARIS_LAT
        lon = PARIS_LON
        data = [
            CellArea(lat=lat, lon=lon, range=1000,
                     radio=Radio.umts, **key),
        ]
        session.add_all(data)
        session.commit()

        res = app.post_json(
            '/v1/search?key=test',
            {
                'radio': Radio.gsm.name,
                'cell': [
                    dict(radio=Radio.umts.name, **key),
                    dict(radio=Radio.umts.name, **key),
                ],
                'fallbacks': {
                    'ipf': 1,
                },
            },
            status=200)

        self.assertEqual(res.content_type, 'application/json')
        self.assertEqual(res.json, {'status': 'ok',
                                    'lat': PARIS_LAT,
                                    'lon': PARIS_LON,
                                    'accuracy': LAC_MIN_ACCURACY,
                                    'fallback': 'lacf'})

        self.check_stats(
            timer=[('request.v1.search', 1)],
            counter=[('search.api_key.test', 1),
                     ('search.cell_lac_hit', 1),
                     ('request.v1.search.200', 1),
                     ('search.api_log.test.cell_lac_hit', 1)],
        )

    def test_cellarea_not_used_when_lacf_disabled(self):
        app = self.app
        session = self.session
        key = dict(mcc=FRANCE_MCC, mnc=2, lac=3)
        lat = PARIS_LAT
        lon = PARIS_LON
        data = [
            CellArea(lat=lat, lon=lon, range=1000,
                     radio=Radio.umts, **key),
        ]
        session.add_all(data)
        session.commit()

        res = app.post_json(
            '/v1/search?key=test',
            {
                'radio': Radio.gsm.name, 'cell': [
                    dict(radio=Radio.umts.name, **key),
                    dict(radio=Radio.umts.name, **key),
                ],
                'fallbacks': {
                    'lacf': 0,
                },
            },
            status=200)

        self.assertEqual(res.content_type, 'application/json')
        self.assertEqual(res.json, {'status': 'not_found'})

        self.check_stats(
            timer=[('request.v1.search', 1)],
            counter=[('search.api_key.test', 1),
                     ('request.v1.search.200', 1)],
        )

    def test_ok_wifi(self):
        app = self.app
        session = self.session
        wifis = [
            Wifi(key='101010101010', lat=1.0, lon=1.0),
            Wifi(key='202020202020', lat=1.002, lon=1.004),
            Wifi(key='303030303030', lat=None, lon=None),
        ]
        session.add_all(wifis)
        session.commit()
        res = app.post_json('/v1/search?key=test',
                            {'wifi': [
                                {'key': '101010101010'},
                                {'key': '202020202020'},
                                {'key': '303030303030'},
                            ]},
                            status=200)
        self.assertEqual(res.content_type, 'application/json')
        self.assertEqual(res.json, {'status': 'ok',
                                    'lat': 1.001, 'lon': 1.002,
                                    'accuracy': 248.6090897})

        self.check_stats(
            timer=[('request.v1.search', 1)],
            counter=[('search.api_key.test', 1),
                     ('search.wifi_hit', 1),
                     ('request.v1.search.200', 1),
                     ('search.api_log.test.wifi_hit', 1)],
        )

    def test_ok_geoip(self):
        london = self.geoip_data['London']
        res = self.app.post_json(
            '/v1/search?key=test',
            {'wifi': [
                {'key': 'a0fffffff0ff'}, {'key': 'b1ffff0fffff'},
                {'key': 'c2fffffffff0'}, {'key': 'd3fffff0ffff'},
            ]},
            extra_environ={'HTTP_X_FORWARDED_FOR': london['ip']},
            status=200)
        self.assertEqual(res.content_type, 'application/json')
        self.assertEqual(res.json, {'status': 'ok',
                                    'lat': london['latitude'],
                                    'lon': london['longitude'],
                                    'accuracy': london['accuracy'],
                                    'fallback': 'ipf'})

        self.check_stats(
            timer=[('request.v1.search', 1)],
            counter=[('search.api_key.test', 1),
                     ('search.geoip_hit', 1),
                     ('request.v1.search.200', 1),
                     ('search.geoip_city_found', 1),
                     ('search.api_log.test.wifi_miss', 1)],
        )

    def test_geoip_not_used_when_ipf_disabled(self):
        london = self.geoip_data['London']
        res = self.app.post_json(
            '/v1/search?key=test',
            {
                'wifi': [
                    {'key': 'a0fffffff0ff'}, {'key': 'b1ffff0fffff'},
                    {'key': 'c2fffffffff0'}, {'key': 'd3fffff0ffff'},
                ],
                'fallbacks': {
                    'ipf': 0,
                },
            },
            extra_environ={'HTTP_X_FORWARDED_FOR': london['ip']},
            status=200)
        self.assertEqual(res.content_type, 'application/json')
        self.assertEqual(res.json, {'status': 'not_found'})

        self.check_stats(
            timer=[('request.v1.search', 1)],
            counter=[('search.api_key.test', 1),
                     ('request.v1.search.200', 1),
                     ('search.api_log.test.wifi_miss', 1)],
        )

    def test_ok_fallback(self):
        cell_key = dict(mcc=FRANCE_MCC, mnc=2, lac=3)
        api_key = ApiKey.getkey(self.session, 'test')
        api_key.allow_fallback = True
        self.session.commit()

        with requests_mock.Mocker() as mock:
            response_location = {
                'location': {
                    'lat': 1.0,
                    'lng': 1.0,
                },
                'accuracy': 100,
            }
            mock.register_uri(
                'POST', requests_mock.ANY, json=response_location)

            res = self.app.post_json(
                '/v1/search?key=test',
                {'radio': Radio.gsm.name, 'cell': [
                    dict(radio=Radio.umts.name, cid=4, **cell_key),
                    dict(radio=Radio.umts.name, cid=5, **cell_key),
                ]},
                status=200)

            send_json = mock.request_history[0].json()
            self.assertEqual(len(send_json['cellTowers']), 2)
            self.assertEqual(send_json['cellTowers'][0]['radioType'], 'wcdma')

        self.assertEqual(res.content_type, 'application/json')
        self.assertEqual(res.json, {'status': 'ok',
                                    'lat': 1.0,
                                    'lon': 1.0,
                                    'accuracy': 100})

        self.check_stats(
            timer=[('request.v1.search', 1)],
            counter=[('search.api_key.test', 1),
                     ('search.fallback_hit', 1),
                     ('request.v1.search.200', 1),
                     ('search.api_log.test.fallback_hit', 1)],
        )

    def test_fallback_used_when_geoip_also_present(self):
        london = self.geoip_data['London']
        cell_key = dict(mcc=FRANCE_MCC, mnc=2, lac=3)
        api_key = ApiKey.getkey(self.session, 'test')
        api_key.allow_fallback = True
        self.session.commit()

        with requests_mock.Mocker() as mock:
            response_location = {
                'location': {
                    'lat': 1.0,
                    'lng': 1.0,
                },
                'accuracy': 100,
            }
            mock.register_uri(
                'POST', requests_mock.ANY, json=response_location)

            res = self.app.post_json(
                '/v1/search?key=test',
                {'radio': Radio.gsm.name, 'cell': [
                    dict(radio=Radio.umts.name, cid=4, **cell_key),
                    dict(radio=Radio.umts.name, cid=5, **cell_key),
                ]},
                extra_environ={'HTTP_X_FORWARDED_FOR': london['ip']},
                status=200)

            send_json = mock.request_history[0].json()
            self.assertEqual(len(send_json['cellTowers']), 2)
            self.assertEqual(send_json['cellTowers'][0]['radioType'], 'wcdma')

        self.assertEqual(res.content_type, 'application/json')
        self.assertEqual(res.json, {'status': 'ok',
                                    'lat': 1.0,
                                    'lon': 1.0,
                                    'accuracy': 100})

        self.check_stats(
            timer=[('request.v1.search', 1)],
            counter=[('search.api_key.test', 1),
                     ('search.fallback_hit', 1),
                     ('request.v1.search.200', 1),
                     ('search.api_log.test.fallback_hit', 1)],
        )

    def test_not_found(self):
        app = self.app
        res = app.post_json('/v1/search?key=test',
                            {'cell': [{'mcc': FRANCE_MCC, 'mnc': 2,
                                       'lac': 3, 'cid': 4}]},
                            status=200)
        self.assertEqual(res.content_type, 'application/json')
        self.assertEqual(res.json, {'status': 'not_found'})

        self.check_stats(counter=['search.api_key.test',
                                  'search.miss'])

    def test_wifi_not_found(self):
        app = self.app
        res = app.post_json('/v1/search?key=test', {'wifi': [
                            {'key': '101010101010'},
                            {'key': '202020202020'}]},
                            status=200)
        self.assertEqual(res.content_type, 'application/json')
        self.assertEqual(res.json, {'status': 'not_found'})

        self.check_stats(counter=['search.api_key.test',
                                  'search.miss',
                                  'search.api_log.test.wifi_miss'])

    def test_empty_request_means_geoip(self):
        app = self.app
        london = self.geoip_data['London']
        res = app.post_json(
            '/v1/search?key=test', {},
            extra_environ={'HTTP_X_FORWARDED_FOR': london['ip']},
            status=200)
        self.assertEqual(res.content_type, 'application/json')
        self.assertEqual(res.json, {'status': 'ok',
                                    'lat': london['latitude'],
                                    'lon': london['longitude'],
                                    'accuracy': london['accuracy'],
                                    'fallback': 'ipf'})

        self.check_stats(
            timer=[('request.v1.search', 1)],
            counter=[('search.api_key.test', 1),
                     ('search.geoip_hit', 1),
                     ('request.v1.search.200', 1),
                     ('search.geoip_city_found', 1),
                     ('search.api_log.test.geoip_hit', 1)],
        )

    def test_error(self):
        app = self.app
        res = app.post_json('/v1/search?key=test', {'cell': 1}, status=400)
        self.assertEqual(res.content_type, 'application/json')
        self.assertTrue('errors' in res.json)
        self.assertFalse('status' in res.json)

    def test_error_unknown_key(self):
        app = self.app
        res = app.post_json('/v1/search?key=test', {'foo': 0}, status=200)
        self.assertEqual(res.content_type, 'application/json')
        self.assertEqual(res.json, {'status': 'not_found'})

    def test_error_no_mapping(self):
        app = self.app
        res = app.post_json('/v1/search?key=test', [1], status=200)
        self.assertEqual(res.content_type, 'application/json')
        self.assertEqual(res.json, {'status': 'not_found'})

    def test_no_valid_keys(self):
        app = self.app
        res = app.post_json('/v1/search?key=test', {'wifi': [
                            {'key': ':'}, {'key': '.-'}]},
                            status=200)
        self.assertEqual(res.json, {'status': 'not_found'})

    def test_no_json(self):
        app = self.app
        res = app.post('/v1/search?key=test', '\xae', status=400)
        self.assertTrue('errors' in res.json)
        self.check_stats(counter=['search.api_key.test'])

    def test_gzip(self):
        app = self.app
        data = {'cell': [{'mcc': FRANCE_MCC, 'mnc': 2, 'lac': 3, 'cid': 4}]}
        body = util.encode_gzip(dumps(data))
        headers = {
            'Content-Encoding': 'gzip',
        }
        res = app.post('/v1/search?key=test', body, headers=headers,
                       content_type='application/json', status=200)
        self.assertEqual(res.content_type, 'application/json')
        self.assertEqual(res.json, {'status': 'not_found'})

    def test_no_api_key(self):
        app = self.app
        session = self.session
        key = dict(mcc=FRANCE_MCC, mnc=2, lac=3, cid=4)
        session.add(Cell(
            lat=PARIS_LAT,
            lon=PARIS_LON,
            range=1000,
            radio=Radio.umts, **key)
        )
        session.commit()

        res = app.post_json(
            '/v1/search',
            {'radio': Radio.gsm.name, 'cell': [
                dict(radio=Radio.umts.name, **key),
            ]},
            status=400)
        self.assertEqual(res.json, loads(INVALID_API_KEY))
        self.check_stats(counter=['search.no_api_key'])

    def test_unknown_api_key(self):
        app = self.app
        session = self.session
        key = dict(mcc=FRANCE_MCC, mnc=2, lac=3, cid=4)
        session.add(Cell(
            lat=PARIS_LAT,
            lon=PARIS_LON,
            range=1000,
            radio=Radio.umts, **key)
        )
        session.commit()

        res = app.post_json(
            '/v1/search?key=unknown_key',
            {'radio': Radio.gsm.name, 'cell': [
                dict(radio=Radio.umts.name, **key),
            ]},
            status=400)
        self.assertEqual(res.json, loads(INVALID_API_KEY))
        self.check_stats(counter=['search.unknown_api_key'])


class TestErrors(AppTestCase):
    # this is a standalone class to ensure DB isolation for dropping tables

    def tearDown(self):
        self.setup_tables(self.db_rw.engine)
        super(TestErrors, self).tearDown()

    def test_database_error(self):
        app = self.app
        london = self.geoip_data['London']
        session = self.session
        stmt = text('drop table wifi;')
        session.execute(stmt)

        res = app.post_json(
            '/v1/search?key=test',
            {'wifi': [
                {'key': '101010101010'},
                {'key': '202020202020'},
                {'key': '303030303030'},
                {'key': '404040404040'},
            ]},
            extra_environ={'HTTP_X_FORWARDED_FOR': london['ip']},
        )

        self.assertEqual(res.json, {'status': 'ok',
                                    'lat': london['latitude'],
                                    'lon': london['longitude'],
                                    'accuracy': london['accuracy'],
                                    'fallback': 'ipf'})

        self.check_stats(
            timer=['request.v1.search'],
            counter=[
                'request.v1.search.200',
                'search.geoip_hit',
            ],
        )
        self.check_raven(['ProgrammingError'])
