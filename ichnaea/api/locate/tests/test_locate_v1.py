import colander
import pytest
from sqlalchemy import text

from ichnaea.api.locate.constants import (
    BLUE_MIN_ACCURACY,
    CELL_MIN_ACCURACY,
    WIFI_MIN_ACCURACY,
)
from ichnaea.api.locate.schema_v1 import LOCATE_V1_SCHEMA
from ichnaea.api.locate.tests.base import (
    BaseLocateTest,
    CommonLocateTest,
    CommonPositionTest,
)
from ichnaea.conftest import GEOIP_DATA
from ichnaea.models import (
    ApiKey,
    CellArea,
    Radio,
)
from ichnaea.tests.factories import (
    BlueShardFactory,
    CellShardFactory,
    WifiShardFactory,
)


class TestSchema(object):

    def test_empty(self):
        data = LOCATE_V1_SCHEMA.deserialize({})
        assert (data == {
            'bluetoothBeacons': (),
            'carrier': None,
            'cellTowers': (),
            'considerIp': True,
            'fallbacks': {'ipf': True, 'lacf': True},
            'homeMobileCountryCode': None,
            'homeMobileNetworkCode': None,
            'wifiAccessPoints': ()})

    def test_consider_ip(self):
        data = LOCATE_V1_SCHEMA.deserialize({'considerIp': False})
        assert data['fallbacks']['ipf'] is False
        data = LOCATE_V1_SCHEMA.deserialize({'considerIp': 'false'})
        assert data['fallbacks']['ipf'] is False
        data = LOCATE_V1_SCHEMA.deserialize({'considerIp': 'true'})
        assert data['fallbacks']['ipf'] is True
        data = LOCATE_V1_SCHEMA.deserialize(
            {'considerIp': False, 'fallbacks': {}})
        assert data['fallbacks']['ipf'] is True

    def test_invalid_radio_field(self):
        with pytest.raises(colander.Invalid):
            LOCATE_V1_SCHEMA.deserialize({'cellTowers': [{
                'radioType': 'umts',
            }]})

    def test_multiple_radio_fields(self):
        data = LOCATE_V1_SCHEMA.deserialize({'cellTowers': [{
            'radio': 'gsm',
            'radioType': 'wcdma',
        }]})
        assert data['cellTowers'][0]['radioType'] == 'wcdma'
        assert 'radio' not in data['cellTowers'][0]


class LocateV1Base(BaseLocateTest):

    url = '/v1/geolocate'
    metric_path = 'path:v1.geolocate'
    metric_type = 'locate'

    @property
    def ip_response(self):
        london = GEOIP_DATA['London']
        return {
            'location': {'lat': london['latitude'],
                         'lng': london['longitude']},
            'accuracy': london['radius'],
        }

    def check_model_response(self, response, model,
                             region=None, fallback=None, **kw):
        expected_names = set(['location', 'accuracy'])

        expected = super(LocateV1Base, self).check_model_response(
            response, model,
            region=region,
            fallback=fallback,
            expected_names=expected_names,
            **kw)

        data = response.json
        location = data['location']
        assert round(location['lat'], 7) == round(expected['lat'], 7)
        assert round(location['lng'], 7) == round(expected['lon'], 7)
        assert data['accuracy'] == expected['accuracy']
        if fallback is not None:
            assert data['fallback'] == fallback


class TestView(LocateV1Base, CommonLocateTest, CommonPositionTest):

    def test_blue(self, app, data_queues, session, stats):
        blue = BlueShardFactory()
        offset = 0.00001
        blues = [
            blue,
            BlueShardFactory(lat=blue.lat + offset),
            BlueShardFactory(lat=blue.lat + offset * 2),
            BlueShardFactory(lat=None, lon=None),
        ]
        session.flush()

        query = self.model_query(blues=blues)
        blue_query = query['bluetoothBeacons']
        blue_query[0]['signalStrength'] = -50
        blue_query[1]['signalStrength'] = -150
        blue_query[1]['name'] = 'my-beacon'

        res = self._call(app, body=query)
        self.check_model_response(res, blue, lat=blue.lat + 0.0000035)
        self.check_queue(data_queues, 1)
        stats.check(counter=[
            (self.metric_type + '.request', [self.metric_path, 'key:test']),
            (self.metric_type + '.result',
                ['key:test', 'region:none', 'fallback_allowed:false',
                 'accuracy:high', 'status:hit', 'source:internal']),
            (self.metric_type + '.source',
                ['key:test', 'region:none', 'source:internal',
                 'accuracy:high', 'status:hit']),
        ])
        items = data_queues['update_incoming'].dequeue()
        assert (items == [{
            'api_key': 'test',
            'source': 'query',
            'report': {
                'bluetoothBeacons': [{
                    'macAddress': blue_query[0]['macAddress'],
                    'signalStrength': -50
                }, {
                    'macAddress': blue_query[1]['macAddress'],
                    'name': 'my-beacon',
                }, {
                    'macAddress': blue_query[2]['macAddress'],
                }, {
                    'macAddress': blue_query[3]['macAddress'],
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

    def test_blue_seen(self, app, data_queues, session):
        blue = BlueShardFactory()
        offset = 0.00002
        blues = [
            blue,
            BlueShardFactory(lat=blue.lat + offset),
        ]
        session.flush()
        query = self.model_query(blues=blues)
        res = self._call(app, body=query)
        self.check_model_response(res, blue, lat=blue.lat + offset / 2)
        self.check_queue(data_queues, 0)

    def test_cell(self, app, data_queues, session, stats):
        cell = CellShardFactory(radio=Radio.lte)
        session.flush()

        query = self.model_query(cells=[cell])
        query['radioType'] = cell.radio.name
        del query['cellTowers'][0]['radioType']
        query['cellTowers'][0]['signalStrength'] = -70
        query['cellTowers'][0]['timingAdvance'] = 1

        res = self._call(app, body=query)
        self.check_model_response(res, cell)
        self.check_queue(data_queues, 1)
        stats.check(counter=[
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
        items = data_queues['update_incoming'].dequeue()
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

    def test_partial_cell(self, app, data_queues, session):
        cell = CellShardFactory()
        session.flush()

        # simulate one neighboring incomplete cell
        query = self.model_query(cells=[cell])
        query['cellTowers'][0]['psc'] = cell.psc

        cell_two = query['cellTowers'][0].copy()
        del cell_two['locationAreaCode']
        del cell_two['cellId']
        cell_two['psc'] = cell.psc + 1
        query['cellTowers'].append(cell_two)

        res = self._call(app, body=query)
        self.check_model_response(res, cell)
        self.check_queue(data_queues, 1)

    def test_wifi(self, app, data_queues, session, stats):
        wifi = WifiShardFactory()
        offset = 0.00001
        wifis = [
            wifi,
            WifiShardFactory(lat=wifi.lat + offset),
            WifiShardFactory(lat=wifi.lat + offset * 2),
            WifiShardFactory(lat=None, lon=None),
        ]
        session.flush()

        query = self.model_query(wifis=wifis)
        wifi_query = query['wifiAccessPoints']
        wifi_query[0]['channel'] = 1
        wifi_query[0]['signalStrength'] = -50
        wifi_query[1]['frequency'] = 2437
        wifi_query[2]['signalStrength'] = -130
        wifi_query[2]['signalToNoiseRatio'] = 13
        wifi_query[3]['ssid'] = 'my-wifi'

        res = self._call(app, body=query)
        self.check_model_response(res, wifi, lat=wifi.lat + 0.000005)
        self.check_queue(data_queues, 1)
        stats.check(counter=[
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
        items = data_queues['update_incoming'].dequeue()
        assert (items == [{
            'api_key': 'test',
            'source': 'query',
            'report': {
                'wifiAccessPoints': [{
                    'macAddress': wifi_query[0]['macAddress'],
                    'channel': 1,
                    'frequency': 2412,
                    'signalStrength': -50
                }, {
                    'macAddress': wifi_query[1]['macAddress'],
                    'channel': 6,
                    'frequency': 2437,
                }, {
                    'macAddress': wifi_query[2]['macAddress'],
                    'signalToNoiseRatio': 13,
                }, {
                    'macAddress': wifi_query[3]['macAddress'],
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

    def test_cell_mcc_mnc_strings(self, app, session):
        # mcc and mnc are officially defined as strings, where '01' is
        # different from '1'. In practice many systems ours included treat
        # them as integers, so both of these are encoded as 1 instead.
        # Some clients sends us these values as strings, some as integers,
        # so we want to make sure we support both.
        cell = CellShardFactory(mnc=1)
        session.flush()

        query = self.model_query(cells=[cell])
        query['cellTowers'][0]['mobileCountryCode'] = str(cell.mcc)
        query['cellTowers'][0]['mobileNetworkCode'] = '01'

        res = self._call(app, body=query)
        self.check_model_response(res, cell)

    def test_cell_radio_in_celltowers(self, app, session):
        # This test covers a bug related to FxOS calling the
        # geolocate API incorrectly.
        cell = CellShardFactory()
        session.flush()

        query = self.model_query(cells=[cell])
        query['cellTowers'][0]['radio'] = cell.radio.name
        del query['cellTowers'][0]['radioType']

        res = self._call(app, body=query)
        self.check_model_response(res, cell)

    def test_cell_radiotype_in_celltowers(self, app, session):
        # This test covers an extension to the geolocate API
        cell = CellShardFactory()
        session.flush()

        query = self.model_query(cells=[cell])
        query['cellTowers'][0]['radioType'] = cell.radio.name

        res = self._call(app, body=query)
        self.check_model_response(res, cell)

    def test_cell_radio_in_celltowers_dupes(self, app, session):
        # This test covers a bug related to FxOS calling the
        # geolocate API incorrectly.
        cell = CellShardFactory()
        session.flush()

        query = self.model_query(cells=[cell])
        query['cellTowers'][0]['radio'] = cell.radio.name
        del query['cellTowers'][0]['radioType']

        cell_two = query['cellTowers'][0].copy()
        query['cellTowers'].append(cell_two)

        res = self._call(app, body=query)
        self.check_model_response(res, cell)

    def test_inconsistent_cell_radio(self, app, session):
        cell = CellShardFactory(
            radio=Radio.wcdma, radius=15000, samples=10)
        cell2 = CellShardFactory(
            radio=Radio.gsm, radius=35000, samples=5,
            lat=cell.lat + 0.0002, lon=cell.lon)
        session.flush()

        query = self.model_query(cells=[cell, cell2])
        query['radioType'] = Radio.lte.name
        query['cellTowers'][0]['radio'] = 'wcdma'
        query['cellTowers'][1]['radio'] = cell2.radio.name
        del query['cellTowers'][0]['radioType']
        del query['cellTowers'][1]['radioType']

        res = self._call(app, body=query)
        self.check_model_response(res, cell)

    def test_inconsistent_cell_radio_type(self, app, session):
        cell = CellShardFactory(
            radio=Radio.wcdma, radius=15000, samples=10)
        cell2 = CellShardFactory(
            radio=Radio.gsm, radius=35000, samples=5,
            lat=cell.lat + 0.0002, lon=cell.lon)
        session.flush()

        query = self.model_query(cells=[cell, cell2])
        query['radioType'] = Radio.lte.name
        query['cellTowers'][0]['radio'] = 'lte'

        res = self._call(app, body=query)
        self.check_model_response(res, cell)

    def test_cdma_cell(self, app, session):
        # Specifying a CDMA radio type works,
        # but the information is ignored.
        cell = CellShardFactory(
            radio=Radio.gsm, radius=15000)
        cell2 = CellShardFactory(
            radio=Radio.gsm, radius=35000,
            lat=cell.lat + 0.0002, lon=cell.lon)
        cell2.radio = Radio.cdma
        session.flush()

        query = self.model_query(cells=[cell, cell2])
        res = self._call(app, body=query)
        self.check_model_response(res, cell)


class TestError(LocateV1Base, BaseLocateTest):

    def test_apikey_error(self, app, data_queues,
                          raven, session, stats, restore_db):
        cells = CellShardFactory.build_batch(2)
        wifis = WifiShardFactory.build_batch(2)

        session.execute(text('drop table %s;' % ApiKey.__tablename__))

        query = self.model_query(cells=cells, wifis=wifis)
        res = self._call(app, body=query, ip=self.test_ip)
        self.check_response(data_queues, res, 'ok', fallback='ipf')
        raven.check([('ProgrammingError', 1)])
        self.check_queue(data_queues, 0)

    def test_database_error(self, app, data_queues,
                            raven, session, stats, restore_db):
        cells = [
            CellShardFactory.build(radio=Radio.gsm),
            CellShardFactory.build(radio=Radio.wcdma),
            CellShardFactory.build(radio=Radio.lte),
        ]
        wifis = WifiShardFactory.build_batch(2)

        for model in (CellArea, ):
            session.execute(text('drop table %s;' % model.__tablename__))
        for name in set([cell.__tablename__ for cell in cells]):
            session.execute(text('drop table %s;' % name))
        for name in set([wifi.__tablename__ for wifi in wifis]):
            session.execute(text('drop table %s;' % name))

        query = self.model_query(cells=cells, wifis=wifis)
        res = self._call(app, body=query, ip=self.test_ip)
        self.check_response(data_queues, res, 'ok', fallback='ipf')
        self.check_queue(data_queues, 0)
        stats.check(counter=[
            ('request', [self.metric_path, 'method:post', 'status:200']),
        ], timer=[
            ('request', [self.metric_path, 'method:post']),
        ])
        if self.apikey_metrics:
            stats.check(counter=[
                (self.metric_type + '.result',
                    ['key:test', 'region:GB', 'fallback_allowed:false',
                     'accuracy:high', 'status:miss']),
            ])

        raven.check([('ProgrammingError', 3)])
