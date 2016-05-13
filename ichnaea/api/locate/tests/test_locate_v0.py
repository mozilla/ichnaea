import colander
import pytest

from ichnaea.api.exceptions import LocationNotFoundV0
from ichnaea.api.locate.constants import (
    BLUE_MIN_ACCURACY,
    CELL_MIN_ACCURACY,
    WIFI_MIN_ACCURACY,
)
from ichnaea.api.locate.schema_v0 import LOCATE_V0_SCHEMA
from ichnaea.api.locate.tests.base import (
    BaseLocateTest,
    CommonLocateErrorTest,
    CommonLocateTest,
    CommonPositionTest,
)
from ichnaea.models import Radio
from ichnaea.tests.base import (
    AppTestCase,
    GEOIP_DATA,
)
from ichnaea.tests.factories import (
    BlueShardFactory,
    CellShardFactory,
    WifiShardFactory,
)


class TestSchema(object):

    def test_empty(self):
        data = LOCATE_V0_SCHEMA.deserialize({})
        assert (data ==
                {'bluetoothBeacons': (), 'cellTowers': (),
                 'fallbacks': None, 'wifiAccessPoints': ()})

    def test_empty_cell_entry(self):
        data = LOCATE_V0_SCHEMA.deserialize({'cell': [{}]})
        assert 'cellTowers' in data

    def test_wrong_cell_data(self):
        with pytest.raises(colander.Invalid):
            LOCATE_V0_SCHEMA.deserialize(
                {'cell': [{'mcc': 'a', 'mnc': 2, 'lac': 3, 'cid': 4}]})


class LocateV0Base(BaseLocateTest, AppTestCase):

    url = '/v1/search'
    metric_path = 'path:v1.search'
    metric_type = 'locate'
    not_found = LocationNotFoundV0

    @property
    def ip_response(self):
        london = GEOIP_DATA['London']
        return {
            'status': 'ok',
            'lat': london['latitude'],
            'lon': london['longitude'],
            'accuracy': london['radius'],
            'fallback': 'ipf',
        }

    def check_model_response(self, response, model,
                             region=None, fallback=None, **kw):
        expected_names = set(['status', 'lat', 'lon', 'accuracy'])

        expected = super(LocateV0Base, self).check_model_response(
            response, model,
            region=region,
            fallback=fallback,
            expected_names=expected_names,
            **kw)

        data = response.json
        assert data['status'] == 'ok'
        assert round(data['lat'], 7) == round(expected['lat'], 7)
        assert round(data['lon'], 7) == round(expected['lon'], 7)
        assert data['accuracy'] == expected['accuracy']
        if fallback is not None:
            assert data['fallback'] == fallback

    def model_query(self, blues=(), cells=(), wifis=()):
        query = {}
        if blues:
            query['blue'] = []
            for blue in blues:
                query['blue'].append({
                    'key': blue.mac,
                })
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
                if getattr(cell, 'psc', None) is not None:
                    cell_query['psc'] = cell.cid
                query['cell'].append(cell_query)
        if wifis:
            query['wifi'] = []
            for wifi in wifis:
                query['wifi'].append({
                    'key': wifi.mac,
                })
        return query


class TestView(LocateV0Base, CommonLocateTest, CommonPositionTest):

    def test_blue(self):
        blue = BlueShardFactory()
        offset = 0.00001
        blues = [
            blue,
            BlueShardFactory(lat=blue.lat + offset),
            BlueShardFactory(lat=blue.lat + offset * 2),
            BlueShardFactory(lat=None, lon=None),
        ]
        self.session.flush()

        query = self.model_query(blues=blues)
        blue_query = query['blue']
        blue_query[0]['signal'] = -50
        blue_query[1]['signal'] = -150
        blue_query[1]['name'] = 'my-beacon'

        res = self._call(body=query)
        self.check_model_response(res, blue, lat=blue.lat + 0.0000035)
        self.check_queue(1)
        self.check_stats(counter=[
            (self.metric_type + '.request', [self.metric_path, 'key:test']),
            (self.metric_type + '.result',
                ['key:test', 'region:none', 'fallback_allowed:false',
                 'accuracy:high', 'status:hit', 'source:internal']),
            (self.metric_type + '.source',
                ['key:test', 'region:none', 'source:internal',
                 'accuracy:high', 'status:hit']),
        ])
        items = self.queue.dequeue()
        assert (items == [{
            'api_key': 'test',
            'source': 'query',
            'report': {
                'bluetoothBeacons': [{
                    'macAddress': blue_query[0]['key'],
                    'signalStrength': -50
                }, {
                    'macAddress': blue_query[1]['key'],
                    'name': 'my-beacon',
                }, {
                    'macAddress': blue_query[2]['key'],
                }, {
                    'macAddress': blue_query[3]['key'],
                }],
                'fallbacks': {'ipf': True, 'lacf': True},
                'position': {
                    'accuracy': BLUE_MIN_ACCURACY,
                    'latitude': blue.lat + 0.0000035,
                    'longitude': blue.lon,
                    'source': 'query',
                }
            },
        }])

    def test_cell(self):
        cell = CellShardFactory(radio=Radio.lte)
        self.session.flush()

        query = self.model_query(cells=[cell])
        query['radio'] = cell.radio.name
        query['cell'][0]['psc'] = cell.psc
        query['cell'][0]['signal'] = -70
        query['cell'][0]['ta'] = 1

        res = self._call(body=query)
        self.check_model_response(res, cell)
        self.check_queue(1)
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
        items = self.queue.dequeue()
        assert (items == [{
            'api_key': 'test',
            'source': 'query',
            'report': {
                'cellTowers': [{
                    'radioType': cell.radio.name,
                    'mobileCountryCode': cell.mcc,
                    'mobileNetworkCode': cell.mnc,
                    'locationAreaCode': cell.lac,
                    'cellId': cell.cid,
                    'primaryScramblingCode': cell.psc,
                    'signalStrength': -70,
                    'timingAdvance': 1,
                }],
                'fallbacks': {'ipf': True, 'lacf': True},
                'position': {
                    'accuracy': CELL_MIN_ACCURACY,
                    'latitude': cell.lat,
                    'longitude': cell.lon,
                    'source': 'query',
                }
            },
        }])

    def test_wifi(self):
        wifi = WifiShardFactory()
        offset = 0.00001
        wifis = [
            wifi,
            WifiShardFactory(lat=wifi.lat + offset),
            WifiShardFactory(lat=wifi.lat + offset * 2),
            WifiShardFactory(lat=None, lon=None),
        ]
        self.session.flush()

        query = self.model_query(wifis=wifis)
        wifi_query = query['wifi']
        wifi_query[0]['channel'] = 1
        wifi_query[0]['signal'] = -50
        wifi_query[1]['frequency'] = 2437
        wifi_query[2]['signal'] = -130
        wifi_query[2]['signalToNoiseRatio'] = 13
        wifi_query[3]['ssid'] = 'my-wifi'

        res = self._call(body=query)
        self.check_model_response(res, wifi, lat=wifi.lat + 0.000005)
        self.check_queue(1)
        self.check_stats(counter=[
            (self.metric_type + '.request', [self.metric_path, 'key:test']),
            (self.metric_type + '.result',
                ['key:test', 'region:none', 'fallback_allowed:false',
                 'accuracy:high', 'status:hit', 'source:internal']),
            (self.metric_type + '.source',
                ['key:test', 'region:none', 'source:internal',
                 'accuracy:high', 'status:hit']),
        ])
        items = self.queue.dequeue()
        assert (items == [{
            'api_key': 'test',
            'source': 'query',
            'report': {
                'wifiAccessPoints': [{
                    'macAddress': wifi_query[0]['key'],
                    'channel': 1,
                    'frequency': 2412,
                    'signalStrength': -50
                }, {
                    'macAddress': wifi_query[1]['key'],
                    'channel': 6,
                    'frequency': 2437,
                }, {
                    'macAddress': wifi_query[2]['key'],
                    'signalToNoiseRatio': 13,
                }, {
                    'macAddress': wifi_query[3]['key'],
                    'ssid': 'my-wifi',
                }],
                'fallbacks': {'ipf': True, 'lacf': True},
                'position': {
                    'accuracy': WIFI_MIN_ACCURACY,
                    'latitude': wifi.lat + 0.000005,
                    'longitude': wifi.lon,
                    'source': 'query',
                }
            },
        }])


class TestError(LocateV0Base, CommonLocateErrorTest):

    def test_apikey_error(self):
        super(TestError, self).test_apikey_error(db_errors=1)

    def test_database_error(self):
        super(TestError, self).test_database_error(db_errors=5)
