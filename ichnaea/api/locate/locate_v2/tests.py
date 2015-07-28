import colander

from ichnaea.models import Radio
from ichnaea.api.locate.locate_v2.schema import LocateV2Schema
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
    WifiFactory,
)


class TestSchema(TestCase):

    def test_empty(self):
        schema = LocateV2Schema()
        data = schema.deserialize({})
        self.assertEqual(data, {
            'carrier': None,
            'cell': (),
            'fallbacks': None,
            'homeMobileCountryCode': None,
            'homeMobileNetworkCode': None,
            'wifi': ()})

    def test_invalid_radio_field(self):
        schema = LocateV2Schema()
        with self.assertRaises(colander.Invalid):
            schema.deserialize({'cellTowers': [{
                'radioType': 'umts',
            }]})

    def test_multiple_radio_fields(self):
        schema = LocateV2Schema()
        data = schema.deserialize({'cellTowers': [{
            'radio': 'gsm',
            'radioType': 'cdma',
        }]})
        self.assertEqual(data['cell'][0]['radio'], 'cdma')
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
            'accuracy': london['accuracy'],
            'fallback': 'ipf',
        }

    def check_model_response(self, response, model,
                             country=None, fallback=None, **kw):
        expected_names = set(['location', 'accuracy'])

        expected = super(LocateV2Base, self).check_model_response(
            response, model,
            country=country,
            fallback=fallback,
            expected_names=expected_names,
            **kw)

        data = response.json
        location = data['location']
        self.assertAlmostEquals(location['lat'], expected['lat'])
        self.assertAlmostEquals(location['lng'], expected['lon'])
        self.assertAlmostEqual(data['accuracy'], expected['accuracy'])
        if fallback is not None:
            self.assertEqual(data['fallback'], fallback)


class TestView(LocateV2Base, CommonLocateTest, CommonPositionTest):

    def test_cell(self):
        cell = CellFactory()
        self.session.flush()

        query = self.model_query(cells=[cell])
        query['radioType'] = cell.radio.name
        del query['cellTowers'][0]['radioType']
        query['cellTowers'][0]['signalStrength'] = -70
        query['cellTowers'][0]['timingAdvance'] = 1

        res = self._call(body=query)
        self.check_model_response(res, cell)
        self.check_stats(counter=[
            (self.metric_type + '.request', [self.metric_path, 'key:test']),
            ('request', [self.metric_path, 'method:post', 'status:200']),
            self.metric_type + '.result.test.all.medium.hit',
            self.metric_type + '.source.test.all.internal.medium.hit',
        ], timer=[
            ('request', [self.metric_path, 'method:post']),
        ])

    def test_partial_cell(self):
        cell = CellFactory()
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
        wifi = WifiFactory()
        offset = 0.0001
        wifis = [
            wifi,
            WifiFactory(lat=wifi.lat + offset),
            WifiFactory(lat=wifi.lat + offset * 2),
            WifiFactory(lat=None, lon=None),
        ]
        self.session.flush()

        query = self.model_query(wifis=wifis)
        wifi_query = query['wifiAccessPoints']
        wifi_query[0]['channel'] = 6
        wifi_query[1]['frequency'] = 2437
        wifi_query[2]['signalStrength'] = -77
        wifi_query[3]['signalToNoiseRatio'] = 13

        res = self._call(body=query)
        self.check_model_response(res, wifi, lat=wifi.lat + offset)

        self.check_stats(counter=[
            (self.metric_type + '.request', [self.metric_path, 'key:test']),
            ('request', [self.metric_path, 'method:post', 'status:200']),
            self.metric_type + '.result.test.all.high.hit',
            self.metric_type + '.source.test.all.internal.high.hit',
        ], timer=[
            ('request', [self.metric_path, 'method:post']),
        ])

    def test_cell_mcc_mnc_strings(self):
        # mcc and mnc are officially defined as strings, where '01' is
        # different from '1'. In practice many systems ours included treat
        # them as integers, so both of these are encoded as 1 instead.
        # Some clients sends us these values as strings, some as integers,
        # so we want to make sure we support both.
        cell = CellFactory(mnc=1)
        self.session.flush()

        query = self.model_query(cells=[cell])
        query['cellTowers'][0]['mobileCountryCode'] = str(cell.mcc)
        query['cellTowers'][0]['mobileNetworkCode'] = '01'

        res = self._call(body=query)
        self.check_model_response(res, cell)

    def test_cell_radio_in_celltowers(self):
        # This test covers a bug related to FxOS calling the
        # geolocate API incorrectly.
        cell = CellFactory()
        self.session.flush()

        query = self.model_query(cells=[cell])
        query['cellTowers'][0]['radio'] = cell.radio.name
        del query['cellTowers'][0]['radioType']

        res = self._call(body=query)
        self.check_model_response(res, cell)

    def test_cell_radiotype_in_celltowers(self):
        # This test covers an extension to the geolocate API
        cell = CellFactory()
        self.session.flush()

        query = self.model_query(cells=[cell])
        query['cellTowers'][0]['radioType'] = cell.radio.name

        res = self._call(body=query)
        self.check_model_response(res, cell)

    def test_cell_radio_in_celltowers_dupes(self):
        # This test covers a bug related to FxOS calling the
        # geolocate API incorrectly.
        cell = CellFactory()
        self.session.flush()

        query = self.model_query(cells=[cell])
        query['cellTowers'][0]['radio'] = cell.radio.name
        del query['cellTowers'][0]['radioType']

        cell_two = query['cellTowers'][0].copy()
        query['cellTowers'].append(cell_two)

        res = self._call(body=query)
        self.check_model_response(res, cell)

    def test_inconsistent_cell_radio(self):
        cell = CellFactory(radio=Radio.wcdma, range=15000)
        cell2 = CellFactory(radio=Radio.gsm, range=35000,
                            lat=cell.lat + 0.0002, lon=cell.lon)
        self.session.flush()

        query = self.model_query(cells=[cell, cell2])
        query['radioType'] = Radio.cdma.name
        query['cellTowers'][0]['radio'] = 'wcdma'
        query['cellTowers'][1]['radio'] = cell2.radio.name
        del query['cellTowers'][0]['radioType']
        del query['cellTowers'][1]['radioType']

        res = self._call(body=query)
        self.check_model_response(res, cell)

    def test_inconsistent_cell_radio_type(self):
        cell = CellFactory(radio=Radio.wcdma, range=15000)
        cell2 = CellFactory(radio=Radio.gsm, range=35000,
                            lat=cell.lat + 0.0002, lon=cell.lon)
        self.session.flush()

        query = self.model_query(cells=[cell, cell2])
        query['radioType'] = Radio.cdma.name
        query['cellTowers'][0]['radio'] = 'cdma'

        res = self._call(body=query)
        self.check_model_response(res, cell)


class TestError(LocateV2Base, CommonLocateErrorTest):

    def test_database_error(self):
        super(TestError, self).test_database_error(db_errors=5)
