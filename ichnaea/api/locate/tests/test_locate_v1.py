import colander

from ichnaea.models import Radio
from ichnaea.api.locate.schema_v1 import LOCATE_V1_SCHEMA
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
    CellShardFactory,
    WifiShardFactory,
)


class TestSchema(TestCase):

    schema = LOCATE_V1_SCHEMA

    def test_empty(self):
        data = self.schema.deserialize({})
        self.assertEqual(data, {
            'carrier': None,
            'cell': (),
            'considerIp': True,
            'fallbacks': {'ipf': True, 'lacf': True},
            'homeMobileCountryCode': None,
            'homeMobileNetworkCode': None,
            'wifi': ()})

    def test_consider_ip(self):
        data = self.schema.deserialize({'considerIp': False})
        self.assertEqual(data['fallbacks']['ipf'], False)
        data = self.schema.deserialize({'considerIp': 'false'})
        self.assertEqual(data['fallbacks']['ipf'], False)
        data = self.schema.deserialize({'considerIp': 'true'})
        self.assertEqual(data['fallbacks']['ipf'], True)
        data = self.schema.deserialize({'considerIp': False, 'fallbacks': {}})
        self.assertEqual(data['fallbacks']['ipf'], True)

    def test_invalid_radio_field(self):
        with self.assertRaises(colander.Invalid):
            self.schema.deserialize({'cellTowers': [{
                'radioType': 'umts',
            }]})

    def test_multiple_radio_fields(self):
        data = self.schema.deserialize({'cellTowers': [{
            'radio': 'gsm',
            'radioType': 'wcdma',
        }]})
        self.assertEqual(data['cell'][0]['radio'], 'wcdma')
        self.assertFalse('radioType' in data['cell'][0])


class LocateV2Base(BaseLocateTest, AppTestCase):

    url = '/v1/geolocate'
    metric_path = 'path:v1.geolocate'
    metric_type = 'locate'

    @property
    def ip_response(self):
        london = self.geoip_data['London']
        return {
            'location': {'lat': london['latitude'],
                         'lng': london['longitude']},
            'accuracy': london['radius'],
            'fallback': 'ipf',
        }

    def check_model_response(self, response, model,
                             region=None, fallback=None, **kw):
        expected_names = set(['location', 'accuracy'])

        expected = super(LocateV2Base, self).check_model_response(
            response, model,
            region=region,
            fallback=fallback,
            expected_names=expected_names,
            **kw)

        data = response.json
        location = data['location']
        self.assertAlmostEqual(location['lat'], expected['lat'])
        self.assertAlmostEqual(location['lng'], expected['lon'])
        self.assertAlmostEqual(data['accuracy'], expected['accuracy'])
        if fallback is not None:
            self.assertEqual(data['fallback'], fallback)


class TestView(LocateV2Base, CommonLocateTest, CommonPositionTest):

    def test_cell(self):
        cell = CellShardFactory()
        self.session.flush()

        query = self.model_query(cells=[cell])
        query['radioType'] = cell.radio.name
        del query['cellTowers'][0]['radioType']
        query['cellTowers'][0]['signalStrength'] = -70
        query['cellTowers'][0]['timingAdvance'] = 1

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

    def test_partial_cell(self):
        cell = CellShardFactory()
        self.session.flush()

        # simulate one neighboring incomplete cell
        query = self.model_query(cells=[cell])
        query['cellTowers'][0]['psc'] = cell.psc

        cell_two = query['cellTowers'][0].copy()
        del cell_two['locationAreaCode']
        del cell_two['cellId']
        cell_two['psc'] = cell.psc + 1
        query['cellTowers'].append(cell_two)

        res = self._call(body=query)
        self.check_model_response(res, cell)

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
        wifi_query = query['wifiAccessPoints']
        wifi_query[0]['channel'] = 6
        wifi_query[1]['frequency'] = 2437
        wifi_query[2]['signalStrength'] = -77
        wifi_query[3]['signalToNoiseRatio'] = 13
        wifi_query[3]['ssid'] = 'my-wifi'

        res = self._call(body=query)
        self.check_model_response(res, wifi, lat=wifi.lat + offset)
        self.check_stats(counter=[
            ('request', [self.metric_path, 'method:post', 'status:200']),
            (self.metric_type + '.request', [self.metric_path, 'key:test']),
            (self.metric_type + '.result',
                ['key:test', 'region:none', 'fallback_allowed:false',
                 'accuracy:high', 'status:hit', 'source:internal']),
            (self.metric_type + '.source',
                ['key:test', 'region:none', 'source:internal',
                 'accuracy:high', 'status:hit']),
        ], timer=[
            ('request', [self.metric_path, 'method:post']),
        ])

    def test_cell_mcc_mnc_strings(self):
        # mcc and mnc are officially defined as strings, where '01' is
        # different from '1'. In practice many systems ours included treat
        # them as integers, so both of these are encoded as 1 instead.
        # Some clients sends us these values as strings, some as integers,
        # so we want to make sure we support both.
        cell = CellShardFactory(mnc=1)
        self.session.flush()

        query = self.model_query(cells=[cell])
        query['cellTowers'][0]['mobileCountryCode'] = str(cell.mcc)
        query['cellTowers'][0]['mobileNetworkCode'] = '01'

        res = self._call(body=query)
        self.check_model_response(res, cell)

    def test_cell_radio_in_celltowers(self):
        # This test covers a bug related to FxOS calling the
        # geolocate API incorrectly.
        cell = CellShardFactory()
        self.session.flush()

        query = self.model_query(cells=[cell])
        query['cellTowers'][0]['radio'] = cell.radio.name
        del query['cellTowers'][0]['radioType']

        res = self._call(body=query)
        self.check_model_response(res, cell)

    def test_cell_radiotype_in_celltowers(self):
        # This test covers an extension to the geolocate API
        cell = CellShardFactory()
        self.session.flush()

        query = self.model_query(cells=[cell])
        query['cellTowers'][0]['radioType'] = cell.radio.name

        res = self._call(body=query)
        self.check_model_response(res, cell)

    def test_cell_radio_in_celltowers_dupes(self):
        # This test covers a bug related to FxOS calling the
        # geolocate API incorrectly.
        cell = CellShardFactory()
        self.session.flush()

        query = self.model_query(cells=[cell])
        query['cellTowers'][0]['radio'] = cell.radio.name
        del query['cellTowers'][0]['radioType']

        cell_two = query['cellTowers'][0].copy()
        query['cellTowers'].append(cell_two)

        res = self._call(body=query)
        self.check_model_response(res, cell)

    def test_inconsistent_cell_radio(self):
        cell = CellShardFactory(radio=Radio.wcdma, radius=15000, samples=10)
        cell2 = CellShardFactory(radio=Radio.gsm, radius=35000, samples=5,
                                 lat=cell.lat + 0.0002, lon=cell.lon)
        self.session.flush()

        query = self.model_query(cells=[cell, cell2])
        query['radioType'] = Radio.lte.name
        query['cellTowers'][0]['radio'] = 'wcdma'
        query['cellTowers'][1]['radio'] = cell2.radio.name
        del query['cellTowers'][0]['radioType']
        del query['cellTowers'][1]['radioType']

        res = self._call(body=query)
        self.check_model_response(res, cell)

    def test_inconsistent_cell_radio_type(self):
        cell = CellShardFactory(radio=Radio.wcdma, radius=15000, samples=10)
        cell2 = CellShardFactory(radio=Radio.gsm, radius=35000, samples=5,
                                 lat=cell.lat + 0.0002, lon=cell.lon)
        self.session.flush()

        query = self.model_query(cells=[cell, cell2])
        query['radioType'] = Radio.lte.name
        query['cellTowers'][0]['radio'] = 'lte'

        res = self._call(body=query)
        self.check_model_response(res, cell)

    def test_cdma_cell(self):
        # Specifying a CDMA radio type works,
        # but the information is ignored.
        cell = CellShardFactory(radio=Radio.gsm, radius=15000)
        cell2 = CellShardFactory(radio=Radio.gsm, radius=35000,
                                 lat=cell.lat + 0.0002, lon=cell.lon)
        cell2.radio = Radio.cdma
        self.session.flush()

        query = self.model_query(cells=[cell, cell2])
        res = self._call(body=query)
        self.check_model_response(res, cell)


class TestError(LocateV2Base, CommonLocateErrorTest):

    def test_apikey_error(self):
        super(TestError, self).test_apikey_error(db_errors=1)

    def test_database_error(self):
        super(TestError, self).test_database_error(db_errors=7)
