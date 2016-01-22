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
from ichnaea.tests.base import ConnectionTestCase
from ichnaea.tests.factories import (
    ApiKeyFactory,
    CellAreaFactory,
    CellShardFactory,
    WifiShardFactory,
)


class QueryTest(ConnectionTestCase):

    @classmethod
    def setUpClass(cls):
        super(QueryTest, cls).setUpClass()
        cls.api_key = ApiKeyFactory.build(shortname='key')
        cls.london = cls.geoip_data['London']
        cls.london_ip = cls.london['ip']

    def cell_model_query(self, cells):
        query = []
        for cell in cells:
            cell_query = {
                'radio': cell.radio.name,
                'mcc': cell.mcc,
                'mnc': cell.mnc,
                'lac': cell.lac,
                'signal': -90,
                'ta': 1,
            }
            if getattr(cell, 'cid', None):
                cell_query['cid'] = cell.cid
                cell_query['psc'] = cell.psc
            query.append(cell_query)
        return query

    def wifi_model_query(self, wifis):
        query = []
        for wifi in wifis:
            query.append({
                'mac': wifi.mac,
                'channel': 11,
                'signal': -85,
                'snr': 13,
            })
        return query


class TestQuery(QueryTest, ConnectionTestCase):

    def test_empty(self):
        query = Query()
        self.assertEqual(query.fallback.ipf, True)
        self.assertEqual(query.fallback.lacf, True)
        self.assertEqual(query.ip, None)
        self.assertEqual(query.cell, [])
        self.assertEqual(query.cell_area, [])
        self.assertEqual(query.wifi, [])
        self.assertEqual(query.api_key, None)
        self.assertEqual(query.api_type, None)
        self.assertEqual(query.session, None)
        self.assertEqual(query.http_session, None)
        self.assertEqual(query.geoip_db, None)
        self.assertEqual(query.stats_client, None)
        self.assertEqual(query.expected_accuracy, DataAccuracy.none)

    def test_fallback(self):
        query = Query(fallback={'ipf': False}, ip=self.london_ip)
        self.assertEqual(query.fallback.ipf, False)
        self.assertEqual(query.fallback.lacf, True)
        self.assertEqual(query.ip, self.london_ip)
        self.assertEqual(query.expected_accuracy, DataAccuracy.none)
        self.assertTrue(query.geoip is None)

    def test_geoip(self):
        query = Query(ip=self.london_ip, geoip_db=self.geoip_db)
        self.assertEqual(query.region, 'GB')
        self.assertEqual(query.geoip['city'], True)
        self.assertEqual(query.geoip['region_code'], 'GB')
        self.assertEqual(query.geoip['region_name'], 'United Kingdom')
        self.assertEqual(query.ip, self.london_ip)
        self.assertEqual(query.expected_accuracy, DataAccuracy.low)

    def test_geoip_malformed(self):
        query = Query(ip='127.0.0.0.0.1', geoip_db=self.geoip_db)
        self.assertEqual(query.region, None)
        self.assertEqual(query.geoip, None)
        self.assertEqual(query.ip, None)

    def test_cell(self):
        cell = CellShardFactory.build()
        cell_query = self.cell_model_query([cell])
        query = Query(cell=cell_query)

        self.assertEqual(len(query.cell), 1)
        self.assertEqual(query.expected_accuracy, DataAccuracy.medium)

        query_cell = query.cell[0]
        for key, value in cell_query[0].items():
            query_value = getattr(query_cell, key, None)
            if key == 'radio':
                self.assertEqual(query_value, cell.radio)
            else:
                self.assertEqual(query_value, value)

        self.assertEqual(len(query.cell_area), 1)
        query_area = query.cell_area[0]
        for key, value in cell_query[0].items():
            query_value = getattr(query_area, key, None)
            if key == 'radio':
                self.assertEqual(query_value, cell.radio)
            elif key in ('cid', 'psc'):
                pass
            else:
                self.assertEqual(query_value, value)

    def test_cell_malformed(self):
        query = Query(cell=[{'radio': 'foo', 'mcc': 'ab'}])
        self.assertEqual(len(query.cell), 0)

    def test_cell_duplicated(self):
        cell = CellShardFactory.build()
        cell_query = self.cell_model_query([cell, cell, cell])
        cell_query[0]['signal'] = -95
        cell_query[1]['signal'] = -90
        cell_query[2]['signal'] = -92
        query = Query(cell=cell_query)
        self.assertEqual(len(query.cell), 1)
        self.assertEqual(query.cell[0].signal, -90)

    def test_cell_region(self):
        cell = CellShardFactory.build()
        cell_query = self.cell_model_query([cell])
        query = Query(cell=cell_query, api_type='region')
        self.assertEqual(query.expected_accuracy, DataAccuracy.low)

    def test_cell_area(self):
        cell = CellAreaFactory.build()
        cell_query = self.cell_model_query([cell])
        query = Query(cell=cell_query)

        self.assertEqual(len(query.cell), 0)
        self.assertEqual(len(query.cell_area), 1)
        self.assertEqual(query.expected_accuracy, DataAccuracy.low)

    def test_cell_area_duplicated(self):
        cell = CellShardFactory.build()
        cell_query = self.cell_model_query([cell, cell, cell])
        cell_query[1]['cid'] += 2
        cell_query[2]['cid'] += 1
        query = Query(cell=cell_query)
        self.assertEqual(len(query.cell), 3)
        self.assertEqual(len(query.cell_area), 1)

    def test_cell_area_no_fallback(self):
        cell = CellAreaFactory.build()
        cell_query = self.cell_model_query([cell])
        query = Query(cell=cell_query, fallback={'lacf': False})

        self.assertEqual(len(query.cell), 0)
        self.assertEqual(len(query.cell_area), 0)
        self.assertEqual(query.expected_accuracy, DataAccuracy.none)

    def test_cell_area_region(self):
        cell = CellAreaFactory.build()
        cell_query = self.cell_model_query([cell])
        query = Query(cell=cell_query, api_type='region')
        self.assertEqual(query.expected_accuracy, DataAccuracy.low)

    def test_cell_area_region_no_fallback(self):
        cell = CellAreaFactory.build()
        cell_query = self.cell_model_query([cell])
        query = Query(cell=cell_query, api_type='region',
                      fallback={'lacf': False})
        self.assertEqual(query.expected_accuracy, DataAccuracy.none)

    def test_wifi(self):
        wifis = WifiShardFactory.build_batch(2)
        macs = [wifi.mac for wifi in wifis]
        query = Query(wifi=self.wifi_model_query(wifis))

        self.assertEqual(len(query.wifi), 2)
        self.assertEqual(query.expected_accuracy, DataAccuracy.high)

        for wifi in query.wifi:
            self.assertEqual(wifi.channel, 11)
            self.assertEqual(wifi.signal, -85)
            self.assertEqual(wifi.snr, 13)
            self.assertTrue(wifi.mac in macs)

    def test_wifi_single(self):
        wifi = WifiShardFactory.build()
        wifi_query = {'mac': wifi.mac}
        query = Query(wifi=[wifi_query])
        self.assertEqual(len(query.wifi), 0)

    def test_wifi_duplicates(self):
        wifi = WifiShardFactory.build()
        query = Query(wifi=[
            {'mac': wifi.mac, 'signal': -90},
            {'mac': wifi.mac, 'signal': -82},
            {'mac': wifi.mac, 'signal': -85},
        ])
        self.assertEqual(len(query.wifi), 0)

    def test_wifi_better(self):
        wifis = WifiShardFactory.build_batch(2)
        query = Query(wifi=[
            {'mac': wifis[0].mac, 'signal': -90, 'channel': 1},
            {'mac': wifis[0].mac, 'signal': -82},
            {'mac': wifis[0].mac, 'signal': -85},
            {'mac': wifis[1].mac, 'signal': -70},
        ])
        self.assertEqual(len(query.wifi), 2)
        self.assertEqual(
            set([wifi.signal for wifi in query.wifi]), set([-70, -82]))

    def test_wifi_malformed(self):
        wifi = WifiShardFactory.build()
        wifi_query = {'mac': wifi.mac}
        query = Query(wifi=[wifi_query, {'mac': 'foo'}])
        self.assertEqual(len(query.wifi), 0)

    def test_wifi_region(self):
        wifis = WifiShardFactory.build_batch(2)
        query = Query(
            wifi=self.wifi_model_query(wifis), api_type='region')
        self.assertEqual(query.expected_accuracy, DataAccuracy.low)

    def test_mixed_cell_wifi(self):
        cells = CellShardFactory.build_batch(1)
        wifis = WifiShardFactory.build_batch(2)

        query = Query(
            cell=self.cell_model_query(cells),
            wifi=self.wifi_model_query(wifis))
        self.assertEqual(query.expected_accuracy, DataAccuracy.high)

    def test_api_key(self):
        api_key = ApiKeyFactory.build()
        query = Query(api_key=api_key)
        self.assertEqual(query.api_key.valid_key, api_key.valid_key)
        self.assertEqual(query.api_key, api_key)

    def test_api_type(self):
        query = Query(api_type='locate')
        self.assertEqual(query.api_type, 'locate')

    def test_api_type_failure(self):
        with self.assertRaises(ValueError):
            Query(api_type='something')

    def test_session(self):
        query = Query(session=self.session)
        self.assertEqual(query.session, self.session)

    def test_stats_client(self):
        query = Query(stats_client=self.stats_client)
        self.assertEqual(query.stats_client, self.stats_client)


class TestQueryStats(QueryTest):

    def _make_query(self, api_key=None, api_type='locate',
                    cell=(), wifi=(), **kw):
        query = Query(
            api_key=api_key or self.api_key,
            api_type=api_type,
            cell=self.cell_model_query(cell),
            wifi=self.wifi_model_query(wifi),
            geoip_db=self.geoip_db,
            stats_client=self.stats_client,
            **kw)
        query.emit_query_stats()
        return query

    def test_no_log(self):
        api_key = ApiKeyFactory.build(shortname='key', log_locate=False)
        self._make_query(api_key=api_key, api_type='locate')
        self.check_stats(total=0)

    def test_no_api_key_shortname(self):
        api_key = ApiKeyFactory.build(shortname=None, log_locate=True)
        cell = CellShardFactory.build()
        self._make_query(api_key=api_key, cell=[cell])
        self.check_stats(counter=[
            ('locate.query',
                ['key:%s' % api_key.valid_key,
                 'region:none', 'geoip:false', 'cell:one', 'wifi:none']),
        ])

    def test_empty(self):
        self._make_query(ip=self.london_ip)
        self.check_stats(counter=[
            ('locate.query',
                ['key:key', 'region:GB', 'cell:none', 'wifi:none']),
        ])

    def test_one(self):
        cells = CellShardFactory.build_batch(1)
        wifis = WifiShardFactory.build_batch(1)

        self._make_query(cell=cells, wifi=wifis, ip=self.london_ip)
        self.check_stats(total=1, counter=[
            ('locate.query',
                ['key:key', 'region:GB', 'cell:one', 'wifi:one']),
        ])

    def test_many(self):
        cells = CellShardFactory.build_batch(2)
        wifis = WifiShardFactory.build_batch(3)

        self._make_query(cell=cells, wifi=wifis, ip=self.london_ip)
        self.check_stats(total=1, counter=[
            ('locate.query',
                ['key:key', 'region:GB', 'cell:many', 'wifi:many']),
        ])


class TestResultStats(QueryTest):

    def _make_result(self, accuracy=None):
        return Position(
            lat=self.london['latitude'],
            lon=self.london['longitude'],
            accuracy=accuracy,
            score=0.5)

    def _make_region_result(self, accuracy=100000.0):
        return Region(
            region_code='GB',
            region_name='United Kingdom',
            accuracy=accuracy,
            score=0.5)

    def _make_query(self, result, api_key=None, api_type='locate',
                    cell=(), wifi=(), **kw):
        query = Query(
            api_key=api_key or self.api_key,
            api_type=api_type,
            cell=self.cell_model_query(cell),
            wifi=self.wifi_model_query(wifi),
            geoip_db=self.geoip_db,
            stats_client=self.stats_client,
            **kw)
        query.emit_result_stats(result)
        return query

    def test_no_log(self):
        api_key = ApiKeyFactory.build(shortname='key', log_locate=False)
        self._make_query(self._make_result(),
                         api_key=api_key, api_type='locate')
        self.check_stats(total=0)

    def test_region_api(self):
        self._make_query(
            self._make_region_result(), api_type='region', ip=self.london_ip)
        self.check_stats(counter=[
            ('region.result',
                ['key:key', 'region:GB', 'fallback_allowed:false',
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
                ['key:key', 'region:GB', 'fallback_allowed:false',
                 'accuracy:low', 'status:miss']),
        ])

    def test_low_miss(self):
        self._make_query(self._make_result(), ip=self.london_ip)
        self.check_stats(counter=[
            ('locate.result',
                ['key:key', 'region:GB', 'fallback_allowed:false',
                 'accuracy:low', 'status:miss']),
        ])

    def test_low_hit(self):
        self._make_query(
            self._make_result(accuracy=25000.0), ip=self.london_ip)
        self.check_stats(counter=[
            ('locate.result',
                ['key:key', 'region:GB', 'fallback_allowed:false',
                 'accuracy:low', 'status:hit']),
        ])

    def test_medium_miss(self):
        cells = CellShardFactory.build_batch(1)
        self._make_query(self._make_result(), cell=cells)
        self.check_stats(counter=[
            ('locate.result',
                ['key:key', 'region:none', 'fallback_allowed:false',
                 'accuracy:medium', 'status:miss']),
        ])

    def test_medium_miss_low(self):
        cells = CellShardFactory.build_batch(1)
        self._make_query(self._make_result(accuracy=50000.1), cell=cells)
        self.check_stats(counter=[
            ('locate.result',
                ['key:key', 'region:none', 'fallback_allowed:false',
                 'accuracy:medium', 'status:miss']),
        ])

    def test_medium_hit(self):
        cells = CellShardFactory.build_batch(1)
        self._make_query(self._make_result(accuracy=50000.0), cell=cells)
        self.check_stats(counter=[
            ('locate.result',
                ['key:key', 'region:none', 'fallback_allowed:false',
                 'accuracy:medium', 'status:hit']),
        ])

    def test_high_miss(self):
        wifis = WifiShardFactory.build_batch(2)
        self._make_query(self._make_result(accuracy=2500.0), wifi=wifis)
        self.check_stats(counter=[
            ('locate.result',
                ['key:key', 'region:none', 'fallback_allowed:false',
                 'accuracy:high', 'status:miss']),
        ])

    def test_high_hit(self):
        wifis = WifiShardFactory.build_batch(2)
        self._make_query(self._make_result(accuracy=1000.0), wifi=wifis)
        self.check_stats(counter=[
            ('locate.result',
                ['key:key', 'region:none', 'fallback_allowed:false',
                 'accuracy:high', 'status:hit']),
        ])

    def test_mixed_miss(self):
        wifis = WifiShardFactory.build_batch(2)
        self._make_query(
            self._make_result(accuracy=2001.0), wifi=wifis, ip=self.london_ip)
        self.check_stats(counter=[
            ('locate.result',
                ['key:key', 'region:GB', 'fallback_allowed:false',
                 'accuracy:high', 'status:miss']),
        ])

    def test_mixed_hit(self):
        cells = CellShardFactory.build_batch(2)
        self._make_query(
            self._make_result(accuracy=500.0), cell=cells, ip=self.london_ip)
        self.check_stats(counter=[
            ('locate.result',
                ['key:key', 'region:GB', 'fallback_allowed:false',
                 'accuracy:medium', 'status:hit']),
        ])


class TestSourceStats(QueryTest, ConnectionTestCase):

    def _make_results(self, accuracy=None):
        return PositionResultList(Position(
            lat=self.london['latitude'],
            lon=self.london['longitude'],
            accuracy=accuracy,
            score=0.5))

    def _make_query(self, source, results, api_key=None, api_type='locate',
                    cell=(), wifi=(), **kw):
        query = Query(
            api_key=api_key or self.api_key,
            api_type=api_type,
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
                ['key:key', 'region:none', 'source:internal',
                 'accuracy:high', 'status:hit']),
        ])

    def test_high_miss(self):
        wifis = WifiShardFactory.build_batch(2)
        results = self._make_results(accuracy=10000.0)
        self._make_query(DataSource.ocid, results, wifi=wifis)
        self.check_stats(counter=[
            ('locate.source',
                ['key:key', 'region:none', 'source:ocid',
                 'accuracy:high', 'status:miss']),
        ])

    def test_no_results(self):
        wifis = WifiShardFactory.build_batch(2)
        results = PositionResultList()
        self._make_query(DataSource.internal, results, wifi=wifis)
        self.check_stats(counter=[
            ('locate.source',
                ['key:key', 'region:none', 'source:internal',
                 'accuracy:high', 'status:miss']),
        ])
