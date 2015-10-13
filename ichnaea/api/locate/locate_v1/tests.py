import colander

from ichnaea.api.exceptions import LocationNotFoundV1
from ichnaea.api.locate.locate_v1.schema import LOCATE_V1_SCHEMA
from ichnaea.api.locate.tests.base import (
    BaseLocateTest,
    CommonLocateErrorTest,
    CommonLocateTest,
    CommonPositionTest,
)
from ichnaea.tests.base import (
    AppTestCase,
    TestCase,
)
from ichnaea.tests.factories import (
    CellFactory,
    WifiShardFactory,
)


class TestSchema(TestCase):

    schema = LOCATE_V1_SCHEMA

    def test_empty(self):
        data = self.schema.deserialize({})
        self.assertEqual(data, {'cell': (), 'fallbacks': None, 'wifi': ()})

    def test_empty_cell_entry(self):
        data = self.schema.deserialize({'cell': [{}]})
        self.assertTrue('cell' in data)

    def test_wrong_cell_data(self):
        with self.assertRaises(colander.Invalid):
            self.schema.deserialize(
                {'cell': [{'mcc': 'a', 'mnc': 2, 'lac': 3, 'cid': 4}]})


class LocateV1Base(BaseLocateTest, AppTestCase):

    url = '/v1/search'
    metric_path = 'path:v1.search'
    metric_type = 'locate'
    not_found = LocationNotFoundV1

    @property
    def ip_response(self):
        london = self.geoip_data['London']
        return {
            'status': 'ok',
            'lat': london['latitude'],
            'lon': london['longitude'],
            'accuracy': london['accuracy'],
            'fallback': 'ipf',
        }

    def check_model_response(self, response, model,
                             region=None, fallback=None, **kw):
        expected_names = set(['status', 'lat', 'lon', 'accuracy'])

        expected = super(LocateV1Base, self).check_model_response(
            response, model,
            region=region,
            fallback=fallback,
            expected_names=expected_names,
            **kw)

        data = response.json
        self.assertEqual(data['status'], 'ok')
        self.assertAlmostEqual(data['lat'], expected['lat'])
        self.assertAlmostEqual(data['lon'], expected['lon'])
        self.assertAlmostEqual(data['accuracy'], expected['accuracy'])
        if fallback is not None:
            self.assertEqual(data['fallback'], fallback)

    def model_query(self, cells=(), wifis=()):
        query = {}
        if cells:
            query['cell'] = []
            for cell in cells:
                cell_query = {
                    'radio': cell.radio.name,
                    'mcc': cell.mcc,
                    'mnc': cell.mnc,
                    'lac': cell.lac,
                }
                if getattr(cell, 'cid', None) is not None:
                    cell_query['cid'] = cell.cid
                query['cell'].append(cell_query)
        if wifis:
            query['wifi'] = []
            for wifi in wifis:
                query['wifi'].append({
                    'key': wifi.mac,
                })
        return query


class TestView(LocateV1Base, CommonLocateTest, CommonPositionTest):

    def test_cell(self):
        cell = CellFactory()
        self.session.flush()

        query = self.model_query(cells=[cell])
        query['radio'] = cell.radio.name
        query['cell'][0]['signal'] = -70
        query['cell'][0]['ta'] = 1

        res = self._call(body=query)
        self.check_model_response(res, cell)
        self.check_stats(counter=[
            ('request', [self.metric_path, 'method:post', 'status:200']),
            (self.metric_type + '.request', [self.metric_path, 'key:test']),
            (self.metric_type + '.result',
                ['key:test', 'region:none', 'fallback_allowed:false',
                 'accuracy:medium', 'status:hit', 'source:internal']),
            (self.metric_type + '.source',
                ['key:test', 'region:none', 'source:internal',
                 'accuracy:medium', 'status:hit']),
        ], timer=[
            ('request', [self.metric_path, 'method:post']),
        ])

    def test_wifi(self):
        wifi = WifiShardFactory()
        offset = 0.0001
        wifis = [
            wifi,
            WifiShardFactory(lat=wifi.lat + offset),
            WifiShardFactory(lat=wifi.lat + offset * 2),
            WifiShardFactory(lat=None, lon=None),
        ]
        self.session.flush()

        query = self.model_query(wifis=wifis)
        wifi_query = query['wifi']
        wifi_query[0]['channel'] = 6
        wifi_query[1]['frequency'] = 2437
        wifi_query[2]['signal'] = -77
        wifi_query[3]['signalToNoiseRatio'] = 13

        res = self._call(body=query)
        self.check_model_response(res, wifi, lat=wifi.lat + offset)

        self.check_stats(counter=[
            (self.metric_type + '.request', [self.metric_path, 'key:test']),
            (self.metric_type + '.result',
                ['key:test', 'region:none', 'fallback_allowed:false',
                 'accuracy:high', 'status:hit', 'source:internal']),
            (self.metric_type + '.source',
                ['key:test', 'region:none', 'source:internal',
                 'accuracy:high', 'status:hit']),
        ])


class TestError(LocateV1Base, CommonLocateErrorTest):

    def test_database_error(self):
        super(TestError, self).test_database_error(db_errors=5)
