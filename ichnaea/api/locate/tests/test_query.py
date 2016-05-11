import pytest

from ichnaea.api.locate.constants import (
    DataAccuracy,
    DataSource,
)
from ichnaea.api.locate.query import Query
from ichnaea.api.locate.result import (
    Position,
    PositionResultList,
    Region,
)
from ichnaea.models import Radio
from ichnaea.tests.base import (
    ConnectionTestCase,
    GEOIP_DATA,
)
from ichnaea.tests.factories import (
    ApiKeyFactory,
    BlueShardFactory,
    CellAreaFactory,
    CellShardFactory,
    WifiShardFactory,
)


class QueryTest(ConnectionTestCase):

    london_ip = GEOIP_DATA['London']['ip']

    def blue_model_query(self, blues):
        query = []
        for blue in blues:
            query.append({
                'macAddress': blue.mac,
                'age': 10,
                'signalStrength': -85,
            })
        return query

    def cell_model_query(self, cells):
        query = []
        for cell in cells:
            cell_query = {
                'radioType': cell.radio.name,
                'mobileCountryCode': cell.mcc,
                'mobileNetworkCode': cell.mnc,
                'locationAreaCode': cell.lac,
                'age': 20,
                'signalStrength': -90,
                'timingAdvance': 1,
            }
            if getattr(cell, 'cid', None):
                cell_query['cellId'] = cell.cid
                cell_query['primaryScramblingCode'] = cell.psc
            query.append(cell_query)
        return query

    def wifi_model_query(self, wifis):
        query = []
        for wifi in wifis:
            query.append({
                'macAddress': wifi.mac,
                'age': 30,
                'frequency': 2412,
                'signalStrength': -85,
                'signalToNoiseRatio': 13,
                'ssid': 'wifi',
            })
        return query


class TestQuery(QueryTest, ConnectionTestCase):

    def test_empty(self):
        query = Query()
        assert query.fallback.ipf is True
        assert query.fallback.lacf is True
        assert query.ip is None
        assert query.blue == []
        assert query.cell == []
        assert query.cell_area == []
        assert query.wifi == []
        assert query.api_key is None
        assert query.api_type is None
        assert query.session is None
        assert query.http_session is None
        assert query.geoip_db is None
        assert query.stats_client is None
        assert query.expected_accuracy is DataAccuracy.none

    def test_fallback(self):
        query = Query(fallback={'ipf': False}, ip=self.london_ip)
        assert query.fallback.ipf is False
        assert query.fallback.lacf is True
        assert query.ip == self.london_ip
        assert query.expected_accuracy is DataAccuracy.none
        assert query.geoip is None

    def test_geoip(self):
        query = Query(ip=self.london_ip, geoip_db=self.geoip_db)
        assert query.region == 'GB'
        assert query.geoip['city'] is True
        assert query.geoip['region_code'] == 'GB'
        assert query.geoip['region_name'] == 'United Kingdom'
        assert query.ip == self.london_ip
        assert query.expected_accuracy is DataAccuracy.low

    def test_geoip_malformed(self):
        query = Query(ip='127.0.0.0.0.1', geoip_db=self.geoip_db)
        assert query.region is None
        assert query.geoip is None
        assert query.ip is None

    def test_blue(self):
        blues = BlueShardFactory.build_batch(2)
        macs = [blue.mac for blue in blues]
        query = Query(blue=self.blue_model_query(blues))

        assert len(query.blue) == 2
        assert query.expected_accuracy is DataAccuracy.high

        for blue in query.blue:
            assert blue.age == 10
            assert blue.signalStrength == -85
            assert blue.macAddress in macs

    def test_blue_single(self):
        blue = BlueShardFactory.build()
        blue_query = {'macAddress': blue.mac}
        query = Query(blue=[blue_query])
        assert len(query.blue) == 0

    def test_blue_duplicates(self):
        blue = BlueShardFactory.build()
        query = Query(blue=[
            {'macAddress': blue.mac, 'signalStrength': -90},
            {'macAddress': blue.mac, 'signalStrength': -82},
            {'macAddress': blue.mac, 'signalStrength': -85},
        ])
        assert len(query.blue) == 0

    def test_blue_better(self):
        blues = BlueShardFactory.build_batch(2)
        query = Query(blue=[
            {'macAddress': blues[0].mac, 'signalStrength': -90,
             'name': 'my-beacon'},
            {'macAddress': blues[0].mac, 'signalStrength': -82},
            {'macAddress': blues[0].mac, 'signalStrength': -85},
            {'macAddress': blues[1].mac, 'signalStrength': -70},
        ])
        assert len(query.blue) == 2
        assert (set([blue.signalStrength for blue in query.blue]) ==
                set([-70, -82]))

    def test_blue_malformed(self):
        blue = BlueShardFactory.build()
        blue_query = {'macAddress': blue.mac}
        query = Query(blue=[blue_query, {'macAddress': 'foo'}])
        assert len(query.blue) == 0

    def test_blue_region(self):
        blues = BlueShardFactory.build_batch(2)
        query = Query(
            blue=self.blue_model_query(blues), api_type='region')
        assert query.expected_accuracy is DataAccuracy.low

    def test_cell(self):
        cell = CellShardFactory.build(radio=Radio.lte)
        cell_query = self.cell_model_query([cell])
        query = Query(cell=cell_query)

        assert len(query.cell) == 1
        assert query.expected_accuracy is DataAccuracy.medium

        query_cell = query.cell[0]
        for key, value in cell_query[0].items():
            query_value = getattr(query_cell, key, None)
            if key == 'radioType':
                assert query_value is cell.radio
            else:
                assert query_value == value

        assert len(query.cell_area) == 1
        query_area = query.cell_area[0]
        for key, value in cell_query[0].items():
            query_value = getattr(query_area, key, None)
            if key == 'radioType':
                assert query_value is cell.radio
            elif key in ('cellId', 'primaryScramblingCode'):
                pass
            else:
                assert query_value == value

    def test_cell_malformed(self):
        query = Query(cell=[{'radioType': 'foo', 'mobileCountryCode': 'ab'}])
        assert len(query.cell) == 0

    def test_cell_duplicated(self):
        cell = CellShardFactory.build()
        cell_query = self.cell_model_query([cell, cell, cell])
        cell_query[0]['signalStrength'] = -95
        cell_query[1]['signalStrength'] = -90
        cell_query[2]['signalStrength'] = -92
        query = Query(cell=cell_query)
        assert len(query.cell) == 1
        assert query.cell[0].signalStrength == -90

    def test_cell_region(self):
        cell = CellShardFactory.build()
        cell_query = self.cell_model_query([cell])
        query = Query(cell=cell_query, api_type='region')
        assert query.expected_accuracy is DataAccuracy.low

    def test_cell_area(self):
        cell = CellAreaFactory.build()
        cell_query = self.cell_model_query([cell])
        query = Query(cell=cell_query)

        assert len(query.cell) == 0
        assert len(query.cell_area) == 1
        assert query.expected_accuracy is DataAccuracy.low

    def test_cell_area_duplicated(self):
        cell = CellShardFactory.build()
        cell_query = self.cell_model_query([cell, cell, cell])
        cell_query[1]['cellId'] += 2
        cell_query[2]['cellId'] += 1
        query = Query(cell=cell_query)
        assert len(query.cell) == 3
        assert len(query.cell_area) == 1

    def test_cell_area_no_fallback(self):
        cell = CellAreaFactory.build()
        cell_query = self.cell_model_query([cell])
        query = Query(cell=cell_query, fallback={'lacf': False})

        assert len(query.cell) == 0
        assert len(query.cell_area) == 0
        assert query.expected_accuracy is DataAccuracy.none

    def test_cell_area_region(self):
        cell = CellAreaFactory.build()
        cell_query = self.cell_model_query([cell])
        query = Query(cell=cell_query, api_type='region')
        assert query.expected_accuracy is DataAccuracy.low

    def test_cell_area_region_no_fallback(self):
        cell = CellAreaFactory.build()
        cell_query = self.cell_model_query([cell])
        query = Query(cell=cell_query, api_type='region',
                      fallback={'lacf': False})
        assert query.expected_accuracy is DataAccuracy.none

    def test_wifi(self):
        wifis = WifiShardFactory.build_batch(2)
        macs = [wifi.mac for wifi in wifis]
        query = Query(wifi=self.wifi_model_query(wifis))

        assert len(query.wifi) == 2
        assert query.expected_accuracy is DataAccuracy.high

        for wifi in query.wifi:
            assert wifi.age == 30
            assert wifi.frequency == 2412
            assert wifi.signalStrength == -85
            assert wifi.signalToNoiseRatio == 13
            assert wifi.macAddress in macs
            assert wifi.ssid == 'wifi'

    def test_wifi_single(self):
        wifi = WifiShardFactory.build()
        wifi_query = {'macAddress': wifi.mac}
        query = Query(wifi=[wifi_query])
        assert len(query.wifi) == 0

    def test_wifi_duplicates(self):
        wifi = WifiShardFactory.build()
        query = Query(wifi=[
            {'macAddress': wifi.mac, 'signalStrength': -90},
            {'macAddress': wifi.mac, 'signalStrength': -82},
            {'macAddress': wifi.mac, 'signalStrength': -85},
        ])
        assert len(query.wifi) == 0

    def test_wifi_better(self):
        wifis = WifiShardFactory.build_batch(2)
        query = Query(wifi=[
            {'macAddress': wifis[0].mac, 'signalStrength': -90,
             'frequency': 1},
            {'macAddress': wifis[0].mac, 'signalStrength': -82},
            {'macAddress': wifis[0].mac, 'signalStrength': -85},
            {'macAddress': wifis[1].mac, 'signalStrength': -70},
        ])
        assert len(query.wifi) == 2
        assert (set([wifi.signalStrength for wifi in query.wifi]) ==
                set([-70, -82]))

    def test_wifi_malformed(self):
        wifi = WifiShardFactory.build()
        wifi_query = {'macAddress': wifi.mac}
        query = Query(wifi=[wifi_query, {'macAddress': 'foo'}])
        assert len(query.wifi) == 0

    def test_wifi_region(self):
        wifis = WifiShardFactory.build_batch(2)
        query = Query(
            wifi=self.wifi_model_query(wifis), api_type='region')
        assert query.expected_accuracy is DataAccuracy.low

    def test_mixed_cell_wifi(self):
        cells = CellShardFactory.build_batch(1)
        wifis = WifiShardFactory.build_batch(2)

        query = Query(
            cell=self.cell_model_query(cells),
            wifi=self.wifi_model_query(wifis))
        assert query.expected_accuracy is DataAccuracy.high

    def test_api_key(self):
        api_key = ApiKeyFactory.build()
        query = Query(api_key=api_key)
        assert query.api_key.valid_key == api_key.valid_key
        assert query.api_key == api_key

    def test_api_type(self):
        query = Query(api_type='locate')
        assert query.api_type == 'locate'

    def test_api_type_failure(self):
        with pytest.raises(ValueError):
            Query(api_type='something')

    def test_session(self):
        query = Query(session=self.session)
        assert query.session == self.session

    def test_stats_client(self):
        query = Query(stats_client=self.stats_client)
        assert query.stats_client == self.stats_client


class TestQueryStats(QueryTest):

    def _make_query(self, api_key=None, api_type='locate',
                    blue=(), cell=(), wifi=(), **kw):
        query = Query(
            api_key=api_key or ApiKeyFactory.build(valid_key='test'),
            api_type=api_type,
            blue=self.blue_model_query(blue),
            cell=self.cell_model_query(cell),
            wifi=self.wifi_model_query(wifi),
            geoip_db=self.geoip_db,
            stats_client=self.stats_client,
            **kw)
        query.emit_query_stats()
        return query

    def test_no_log(self):
        api_key = ApiKeyFactory.build(valid_key=None)
        self._make_query(api_key=api_key, api_type='locate')
        self.check_stats(total=0)

    def test_empty(self):
        self._make_query(ip=self.london_ip)
        self.check_stats(counter=[
            ('locate.query',
                ['key:test', 'region:GB',
                 'blue:none', 'cell:none', 'wifi:none']),
        ])

    def test_one(self):
        blues = BlueShardFactory.build_batch(1)
        cells = CellShardFactory.build_batch(1)
        wifis = WifiShardFactory.build_batch(1)

        self._make_query(blue=blues, cell=cells, wifi=wifis, ip=self.london_ip)
        self.check_stats(total=1, counter=[
            ('locate.query',
                ['key:test', 'region:GB',
                 'blue:one', 'cell:one', 'wifi:one']),
        ])

    def test_many(self):
        blues = BlueShardFactory.build_batch(2)
        cells = CellShardFactory.build_batch(2)
        wifis = WifiShardFactory.build_batch(3)

        self._make_query(blue=blues, cell=cells, wifi=wifis, ip=self.london_ip)
        self.check_stats(total=1, counter=[
            ('locate.query',
                ['key:test', 'region:GB',
                 'blue:many', 'cell:many', 'wifi:many']),
        ])


class TestResultStats(QueryTest):

    def _make_result(self, accuracy=None):
        london = GEOIP_DATA['London']
        return Position(
            lat=london['latitude'],
            lon=london['longitude'],
            accuracy=accuracy,
            score=0.5)

    def _make_region_result(self, accuracy=100000.0):
        return Region(
            region_code='GB',
            region_name='United Kingdom',
            accuracy=accuracy,
            score=0.5)

    def _make_query(self, result, api_key=None, api_type='locate',
                    blue=(), cell=(), wifi=(), **kw):
        query = Query(
            api_key=api_key or ApiKeyFactory.build(valid_key='test'),
            api_type=api_type,
            blue=self.blue_model_query(blue),
            cell=self.cell_model_query(cell),
            wifi=self.wifi_model_query(wifi),
            geoip_db=self.geoip_db,
            stats_client=self.stats_client,
            **kw)
        query.emit_result_stats(result)
        return query

    def test_no_log(self):
        api_key = ApiKeyFactory.build(valid_key=None)
        self._make_query(self._make_result(),
                         api_key=api_key, api_type='locate')
        self.check_stats(total=0)

    def test_region_api(self):
        self._make_query(
            self._make_region_result(), api_type='region', ip=self.london_ip)
        self.check_stats(counter=[
            ('region.result',
                ['key:test', 'region:GB', 'fallback_allowed:false',
                 'accuracy:low', 'status:hit']),
        ])

    def test_no_ip(self):
        self._make_query(
            self._make_result(), ip=self.london_ip, fallback={'ipf': False})
        self.check_stats(total=0)

        self._make_query(None, ip=self.london_ip, fallback={'ipf': False})
        self.check_stats(total=0)

    def test_none(self):
        self._make_query(None, ip=self.london_ip)
        self.check_stats(counter=[
            ('locate.result',
                ['key:test', 'region:GB', 'fallback_allowed:false',
                 'accuracy:low', 'status:miss']),
        ])

    def test_low_miss(self):
        self._make_query(self._make_result(), ip=self.london_ip)
        self.check_stats(counter=[
            ('locate.result',
                ['key:test', 'region:GB', 'fallback_allowed:false',
                 'accuracy:low', 'status:miss']),
        ])

    def test_low_hit(self):
        self._make_query(
            self._make_result(accuracy=25000.0), ip=self.london_ip)
        self.check_stats(counter=[
            ('locate.result',
                ['key:test', 'region:GB', 'fallback_allowed:false',
                 'accuracy:low', 'status:hit']),
        ])

    def test_medium_miss(self):
        cells = CellShardFactory.build_batch(1)
        self._make_query(self._make_result(), cell=cells)
        self.check_stats(counter=[
            ('locate.result',
                ['key:test', 'region:none', 'fallback_allowed:false',
                 'accuracy:medium', 'status:miss']),
        ])

    def test_medium_miss_low(self):
        cells = CellShardFactory.build_batch(1)
        self._make_query(self._make_result(accuracy=50000.1), cell=cells)
        self.check_stats(counter=[
            ('locate.result',
                ['key:test', 'region:none', 'fallback_allowed:false',
                 'accuracy:medium', 'status:miss']),
        ])

    def test_medium_hit(self):
        cells = CellShardFactory.build_batch(1)
        self._make_query(self._make_result(accuracy=50000.0), cell=cells)
        self.check_stats(counter=[
            ('locate.result',
                ['key:test', 'region:none', 'fallback_allowed:false',
                 'accuracy:medium', 'status:hit']),
        ])

    def test_high_miss(self):
        wifis = WifiShardFactory.build_batch(2)
        self._make_query(self._make_result(accuracy=2500.0), wifi=wifis)
        self.check_stats(counter=[
            ('locate.result',
                ['key:test', 'region:none', 'fallback_allowed:false',
                 'accuracy:high', 'status:miss']),
        ])

    def test_high_hit(self):
        wifis = WifiShardFactory.build_batch(2)
        self._make_query(self._make_result(accuracy=500.0), wifi=wifis)
        self.check_stats(counter=[
            ('locate.result',
                ['key:test', 'region:none', 'fallback_allowed:false',
                 'accuracy:high', 'status:hit']),
        ])

    def test_mixed_miss(self):
        wifis = WifiShardFactory.build_batch(2)
        self._make_query(
            self._make_result(accuracy=2001.0), wifi=wifis, ip=self.london_ip)
        self.check_stats(counter=[
            ('locate.result',
                ['key:test', 'region:GB', 'fallback_allowed:false',
                 'accuracy:high', 'status:miss']),
        ])

    def test_mixed_hit(self):
        cells = CellShardFactory.build_batch(2)
        self._make_query(
            self._make_result(accuracy=500.0), cell=cells, ip=self.london_ip)
        self.check_stats(counter=[
            ('locate.result',
                ['key:test', 'region:GB', 'fallback_allowed:false',
                 'accuracy:medium', 'status:hit']),
        ])


class TestSourceStats(QueryTest, ConnectionTestCase):

    def _make_results(self, accuracy=None):
        london = GEOIP_DATA['London']
        return PositionResultList(Position(
            lat=london['latitude'],
            lon=london['longitude'],
            accuracy=accuracy,
            score=0.5))

    def _make_query(self, source, results, api_key=None, api_type='locate',
                    blue=(), cell=(), wifi=(), **kw):
        query = Query(
            api_key=api_key or ApiKeyFactory.build(valid_key='test'),
            api_type=api_type,
            blue=self.blue_model_query(blue),
            cell=self.cell_model_query(cell),
            wifi=self.wifi_model_query(wifi),
            geoip_db=self.geoip_db,
            stats_client=self.stats_client,
            **kw)
        query.emit_source_stats(source, results)
        return query

    def test_high_hit(self):
        wifis = WifiShardFactory.build_batch(2)
        results = self._make_results(accuracy=100.0)
        self._make_query(DataSource.internal, results, wifi=wifis)
        self.check_stats(counter=[
            ('locate.source',
                ['key:test', 'region:none', 'source:internal',
                 'accuracy:high', 'status:hit']),
        ])

    def test_high_miss(self):
        wifis = WifiShardFactory.build_batch(2)
        results = self._make_results(accuracy=10000.0)
        self._make_query(DataSource.ocid, results, wifi=wifis)
        self.check_stats(counter=[
            ('locate.source',
                ['key:test', 'region:none', 'source:ocid',
                 'accuracy:high', 'status:miss']),
        ])

    def test_no_results(self):
        wifis = WifiShardFactory.build_batch(2)
        results = PositionResultList()
        self._make_query(DataSource.internal, results, wifi=wifis)
        self.check_stats(counter=[
            ('locate.source',
                ['key:test', 'region:none', 'source:internal',
                 'accuracy:high', 'status:miss']),
        ])
