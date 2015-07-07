import colander
import requests_mock
import simplejson as json
from sqlalchemy import text

from ichnaea.api.exceptions import LocationNotFoundV1
from ichnaea.api.locate.locate_v1.schema import LocateV1Schema
from ichnaea.api.locate.tests.base import (
    BaseLocateTest,
    CommonLocateTest,
)
from ichnaea.constants import CELL_MIN_ACCURACY, LAC_MIN_ACCURACY
from ichnaea.models import (
    ApiKey,
    Cell,
    CellArea,
    Radio,
    Wifi,
)
from ichnaea.tests.base import (
    AppTestCase,
    FRANCE_MCC,
    PARIS_LAT,
    PARIS_LON,
    TestCase,
)
from ichnaea import util


class TestLocateV1Schema(TestCase):

    def test_empty(self):
        schema = LocateV1Schema()
        data = schema.deserialize({})
        self.assertEqual(data, {})

    def test_empty_cell_entry(self):
        schema = LocateV1Schema()
        data = schema.deserialize({'cell': [{}]})
        self.assertTrue('cell' in data)

    def test_wrong_cell_data(self):
        schema = LocateV1Schema()
        with self.assertRaises(colander.Invalid):
            schema.deserialize(
                {'cell': [{'mcc': 'a', 'mnc': 2, 'lac': 3, 'cid': 4}]})


class LocateV1Base(BaseLocateTest):

    url = '/v1/search'
    metric = 'search'
    metric_url = 'request.v1.search'
    not_found = LocationNotFoundV1

    @property
    def ip_response(self):
        london = self.geoip_data['London']
        return {'status': 'ok',
                'lat': london['latitude'],
                'lon': london['longitude'],
                'accuracy': london['accuracy'],
                'fallback': 'ipf'}


class TestLocateV1(AppTestCase, LocateV1Base, CommonLocateTest):

    def check_model_response(self, response, model, fallback=None, **kw):
        expected_names = set(['status', 'lat', 'lon', 'accuracy'])

        expected = super(TestLocateV1, self).check_model_response(
            response, model,
            fallback=fallback,
            expected_names=expected_names,
            **kw)

        data = response.json
        self.assertEqual(data['status'], 'ok')
        self.assertAlmostEquals(data['lat'], expected['lat'])
        self.assertAlmostEquals(data['lon'], expected['lon'])
        self.assertAlmostEqual(data['accuracy'], expected['accuracy'])
        if fallback is not None:
            self.assertEqual(data['fallback'], fallback)

    def test_ok_cell(self):
        key = dict(mcc=FRANCE_MCC, mnc=2, lac=3)
        lat = PARIS_LAT
        lon = PARIS_LON
        cell1 = Cell(lat=lat, lon=lon, range=CELL_MIN_ACCURACY,
                     radio=Radio.umts, cid=4, **key)
        cell2 = Cell(lat=lat + 0.002, lon=lon + 0.004, range=1000,
                     radio=Radio.umts, cid=5, **key)
        self.session.add_all([cell1, cell2])
        self.session.flush()

        res = self._call(body={
            'radio': Radio.gsm.name, 'cell': [
                dict(radio=Radio.umts.name, cid=4, **key),
                dict(radio=Radio.umts.name, cid=5, **key),
            ]})
        self.check_model_response(res, cell1,
                                  lat=cell1.lat + 0.001,
                                  lon=cell1.lon + 0.002)

        self.check_stats(
            timer=[('request.v1.search', 1)],
            counter=[('search.api_key.test', 1),
                     ('search.cell_hit', 1),
                     ('request.v1.search.200', 1),
                     ('search.api_log.test.cell_hit', 1)],
        )

    def test_ok_cellarea_when_fallback_not_set(self):
        key = dict(mcc=FRANCE_MCC, mnc=2, lac=3)
        area = CellArea(lat=PARIS_LAT, lon=PARIS_LON, range=LAC_MIN_ACCURACY,
                        radio=Radio.umts, **key)
        self.session.add(area)
        self.session.flush()

        res = self._call(body={
            'radio': Radio.gsm.name,
            'cell': [
                dict(radio=Radio.umts.name, **key),
                dict(radio=Radio.umts.name, **key),
            ]})
        self.check_model_response(res, area, fallback='lacf')

        self.check_stats(
            timer=[('request.v1.search', 1)],
            counter=[('search.api_key.test', 1),
                     ('search.cell_lac_hit', 1),
                     ('request.v1.search.200', 1),
                     ('search.api_log.test.cell_lac_hit', 1)],
        )

    def test_ok_cellarea_when_fallback_set(self):
        key = dict(mcc=FRANCE_MCC, mnc=2, lac=3)
        area = CellArea(lat=PARIS_LAT, lon=PARIS_LON, range=LAC_MIN_ACCURACY,
                        radio=Radio.umts, **key)
        self.session.add(area)
        self.session.flush()

        res = self._call(body={
            'radio': Radio.gsm.name,
            'cell': [
                dict(radio=Radio.umts.name, **key),
                dict(radio=Radio.umts.name, **key),
            ],
            'fallbacks': {
                'lacf': 1,
            }})
        self.check_model_response(res, area, fallback='lacf')

    def test_ok_cellarea_when_different_fallback_set(self):
        key = dict(mcc=FRANCE_MCC, mnc=2, lac=3)
        area = CellArea(lat=PARIS_LAT, lon=PARIS_LON, range=LAC_MIN_ACCURACY,
                        radio=Radio.umts, **key)
        self.session.add(area)
        self.session.flush()

        res = self._call(body={
            'radio': Radio.gsm.name,
            'cell': [
                dict(radio=Radio.umts.name, **key),
                dict(radio=Radio.umts.name, **key),
            ],
            'fallbacks': {
                'ipf': 1,
            }})
        self.check_model_response(res, area, fallback='lacf')

    def test_cellarea_not_used_when_lacf_disabled(self):
        key = dict(mcc=FRANCE_MCC, mnc=2, lac=3)
        area = CellArea(lat=PARIS_LAT, lon=PARIS_LON, range=LAC_MIN_ACCURACY,
                        radio=Radio.umts, **key)
        self.session.add(area)
        self.session.flush()

        res = self._call(body={
            'radio': Radio.gsm.name, 'cell': [
                dict(radio=Radio.umts.name, **key),
                dict(radio=Radio.umts.name, **key),
            ],
            'fallbacks': {
                'lacf': 0,
            }})
        self.check_response(res, 'not_found')

        self.check_stats(
            timer=[('request.v1.search', 1)],
            counter=[('search.api_key.test', 1),
                     ('request.v1.search.200', 1)],
        )

    def test_ok_wifi(self):
        wifi = Wifi(key='101010101010', lat=1.0, lon=1.0)
        wifis = [
            wifi,
            Wifi(key='202020202020', lat=1.002, lon=1.004),
            Wifi(key='303030303030', lat=None, lon=None),
        ]
        self.session.add_all(wifis)
        self.session.flush()

        res = self._call(body={
            'wifi': [
                {'key': wifi.key},
                {'key': '202020202020'},
                {'key': '303030303030'},
            ]})
        self.check_model_response(res, wifi,
                                  lat=wifi.lat + 0.001,
                                  lon=wifi.lat + 0.002,
                                  accuracy=248.6090897)

        self.check_stats(
            timer=[('request.v1.search', 1)],
            counter=[('search.api_key.test', 1),
                     ('search.wifi_hit', 1),
                     ('request.v1.search.200', 1),
                     ('search.api_log.test.wifi_hit', 1)],
        )

    def test_ok_geoip(self):
        res = self._call(body={
            'wifi': [
                {'key': 'a0fffffff0ff'}, {'key': 'b1ffff0fffff'},
                {'key': 'c2fffffffff0'}, {'key': 'd3fffff0ffff'},
            ]},
            ip=self.test_ip)
        self.check_response(res, 'ok')

        self.check_stats(
            timer=[('request.v1.search', 1)],
            counter=[('search.api_key.test', 1),
                     ('search.geoip_hit', 1),
                     ('request.v1.search.200', 1),
                     ('search.geoip_city_found', 1),
                     ('search.api_log.test.wifi_miss', 1)],
        )

    def test_geoip_not_used_when_ipf_disabled(self):
        res = self._call(body={
            'wifi': [
                {'key': 'a0fffffff0ff'}, {'key': 'b1ffff0fffff'},
                {'key': 'c2fffffffff0'}, {'key': 'd3fffff0ffff'},
            ],
            'fallbacks': {
                'ipf': 0,
            }},
            ip=self.test_ip)
        self.check_response(res, 'not_found')

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

            res = self._call(body={
                'radio': Radio.gsm.name, 'cell': [
                    dict(radio=Radio.umts.name, cid=4, **cell_key),
                    dict(radio=Radio.umts.name, cid=5, **cell_key),
                ]})

            send_json = mock.request_history[0].json()
            self.assertEqual(len(send_json['cellTowers']), 2)
            self.assertEqual(send_json['cellTowers'][0]['radioType'], 'wcdma')

        self.check_model_response(res, None, lat=1.0, lon=1.0, accuracy=100)

        self.check_stats(
            timer=[('request.v1.search', 1)],
            counter=[('search.api_key.test', 1),
                     ('search.fallback_hit', 1),
                     ('request.v1.search.200', 1),
                     ('search.api_log.test.fallback_hit', 1)],
        )

    def test_fallback_used_when_geoip_also_present(self):
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

            res = self._call(body={
                'radio': Radio.gsm.name, 'cell': [
                    dict(radio=Radio.umts.name, cid=4, **cell_key),
                    dict(radio=Radio.umts.name, cid=5, **cell_key),
                ]},
                ip=self.test_ip)

            send_json = mock.request_history[0].json()
            self.assertEqual(len(send_json['cellTowers']), 2)
            self.assertEqual(send_json['cellTowers'][0]['radioType'], 'wcdma')

        self.check_model_response(res, None, lat=1.0, lon=1.0, accuracy=100)

        self.check_stats(
            timer=[('request.v1.search', 1)],
            counter=[('search.api_key.test', 1),
                     ('search.fallback_hit', 1),
                     ('request.v1.search.200', 1),
                     ('search.api_log.test.fallback_hit', 1)],
        )

    def test_not_found(self):
        res = self._call(body={
            'cell': [
                {'mcc': FRANCE_MCC, 'mnc': 2, 'lac': 3, 'cid': 4},
            ]})
        self.check_response(res, 'not_found')

        self.check_stats(
            counter=[('request.v1.search.200', 1),
                     'search.api_key.test',
                     'search.miss'],
        )

    def test_wifi_not_found(self):
        res = self._call(body={
            'wifi': [
                {'key': '101010101010'},
                {'key': '202020202020'},
            ]})
        self.check_response(res, 'not_found')

        self.check_stats(counter=['search.api_key.test',
                                  'search.miss',
                                  'search.api_log.test.wifi_miss'])

    def test_gzip(self):
        data = {'cell': [{'mcc': FRANCE_MCC, 'mnc': 2, 'lac': 3, 'cid': 4}]}
        body = util.encode_gzip(json.dumps(data))
        headers = {
            'Content-Encoding': 'gzip',
        }
        res = self._call(body=body, headers=headers, method='post')
        self.check_response(res, 'not_found')


class TestLocateV1Errors(AppTestCase, LocateV1Base, BaseLocateTest):
    # this is a standalone class to ensure DB isolation for dropping tables

    def tearDown(self):
        self.setup_tables(self.db_rw.engine)
        super(TestLocateV1Errors, self).tearDown()

    def test_database_error(self):
        stmt = text('drop table wifi;')
        self.session.execute(stmt)

        res = self._call(body={
            'wifi': [
                {'key': '101010101010'},
                {'key': '202020202020'},
                {'key': '303030303030'},
                {'key': '404040404040'},
            ]},
            ip=self.test_ip)
        self.check_response(res, 'ok')

        self.check_stats(
            timer=['request.v1.search'],
            counter=[
                'request.v1.search.200',
                'search.geoip_hit',
            ],
        )
        self.check_raven(['ProgrammingError'])
