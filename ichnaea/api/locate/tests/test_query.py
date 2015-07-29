from ichnaea.api.locate.constants import (
    DataAccuracy,
    DataSource,
)
from ichnaea.api.locate.query import Query
from ichnaea.api.locate.result import Position
from ichnaea.tests.base import ConnectionTestCase
from ichnaea.tests.factories import (
    ApiKeyFactory,
    CellAreaFactory,
    CellFactory,
    WifiFactory,
)


class QueryTest(ConnectionTestCase):

    @classmethod
    def setUpClass(cls):
        super(QueryTest, cls).setUpClass()
        cls.api_key = ApiKeyFactory.build(shortname='key', log=True)
        cls.london_ip = cls.geoip_data['London']['ip']

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
                'key': wifi.key,
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
        self.assertEqual(query.country, 'GB')
        self.assertEqual(query.geoip['city'], True)
        self.assertEqual(query.geoip['country_code'], 'GB')
        self.assertEqual(query.geoip['country_name'], 'United Kingdom')
        self.assertEqual(query.ip, self.london_ip)
        self.assertEqual(query.expected_accuracy, DataAccuracy.low)

    def test_geoip_malformed(self):
        query = Query(ip='127.0.0.0.0.1', geoip_db=self.geoip_db)
        self.assertEqual(query.country, None)
        self.assertEqual(query.geoip, None)
        self.assertEqual(query.ip, None)

    def test_cell(self):
        cell = CellFactory.build()
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
        cell = CellFactory.build()
        cell_query = self.cell_model_query([cell, cell, cell])
        cell_query[0]['signal'] = -95
        cell_query[1]['signal'] = -90
        cell_query[2]['signal'] = -92
        query = Query(cell=cell_query)
        self.assertEqual(len(query.cell), 1)
        self.assertEqual(query.cell[0].signal, -90)

    def test_cell_country(self):
        cell = CellFactory.build()
        cell_query = self.cell_model_query([cell])
        query = Query(cell=cell_query, api_type='country')
        self.assertEqual(query.expected_accuracy, DataAccuracy.low)

    def test_cell_area(self):
        cell = CellAreaFactory.build()
        cell_query = self.cell_model_query([cell])
        query = Query(cell=cell_query)

        self.assertEqual(len(query.cell), 0)
        self.assertEqual(len(query.cell_area), 1)
        self.assertEqual(query.expected_accuracy, DataAccuracy.low)

    def test_cell_area_duplicated(self):
        cell = CellFactory.build()
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

    def test_cell_area_country(self):
        cell = CellAreaFactory.build()
        cell_query = self.cell_model_query([cell])
        query = Query(cell=cell_query, api_type='country')
        self.assertEqual(query.expected_accuracy, DataAccuracy.low)

    def test_cell_area_country_no_fallback(self):
        cell = CellAreaFactory.build()
        cell_query = self.cell_model_query([cell])
        query = Query(cell=cell_query, api_type='country',
                      fallback={'lacf': False})
        self.assertEqual(query.expected_accuracy, DataAccuracy.none)

    def test_wifi(self):
        wifis = WifiFactory.build_batch(2)
        wifi_keys = [wifi.key for wifi in wifis]
        query = Query(wifi=self.wifi_model_query(wifis))

        self.assertEqual(len(query.wifi), 2)
        self.assertEqual(query.expected_accuracy, DataAccuracy.high)

        for wifi in query.wifi:
            self.assertEqual(wifi.channel, 11)
            self.assertEqual(wifi.signal, -85)
            self.assertEqual(wifi.snr, 13)
            self.assertTrue(wifi.key in wifi_keys)

    def test_wifi_single(self):
        wifi = WifiFactory.build()
        wifi_query = {'key': wifi.key}
        query = Query(wifi=[wifi_query])
        self.assertEqual(len(query.wifi), 0)

    def test_wifi_duplicates(self):
        wifi = WifiFactory.build()
        query = Query(wifi=[
            {'key': wifi.key, 'signal': -90},
            {'key': wifi.key, 'signal': -82},
            {'key': wifi.key, 'signal': -85},
        ])
        self.assertEqual(len(query.wifi), 0)

    def test_wifi_better(self):
        wifis = WifiFactory.build_batch(2)
        query = Query(wifi=[
            {'key': wifis[0].key, 'signal': -90, 'channel': 1},
            {'key': wifis[0].key, 'signal': -82},
            {'key': wifis[0].key, 'signal': -85},
            {'key': wifis[1].key, 'signal': -70},
        ])
        self.assertEqual(len(query.wifi), 2)
        self.assertEqual(
            set([wifi.signal for wifi in query.wifi]), set([-70, -82]))

    def test_wifi_malformed(self):
        wifi = WifiFactory.build()
        wifi_query = {'key': wifi.key}
        query = Query(wifi=[wifi_query, {'key': 'foo'}])
        self.assertEqual(len(query.wifi), 0)

    def test_wifi_country(self):
        wifis = WifiFactory.build_batch(2)
        query = Query(
            wifi=self.wifi_model_query(wifis), api_type='country')
        self.assertEqual(query.expected_accuracy, DataAccuracy.none)

    def test_mixed_cell_wifi(self):
        cells = CellFactory.build_batch(1)
        wifis = WifiFactory.build_batch(2)

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
        api_key = ApiKeyFactory.build(shortname='key', log=False)
        self._make_query(api_key=api_key)
        self.check_stats(total=0)

    def test_no_api_key_shortname(self):
        api_key = ApiKeyFactory.build(shortname=None, log=True)
        cell = CellFactory.build()
        self._make_query(api_key=api_key, cell=[cell])
        self.check_stats(counter=[
            ('locate.query',
                ['key:%s' % api_key.valid_key,
                 'country:none', 'geoip:false', 'cell:one', 'wifi:none']),
        ])

    def test_empty(self):
        self._make_query(ip=self.london_ip)
        self.check_stats(counter=[
            ('locate.query',
                ['key:key', 'country:xx', 'cell:none', 'wifi:none']),
        ])

    def test_one(self):
        cells = CellFactory.build_batch(1)
        wifis = WifiFactory.build_batch(1)

        self._make_query(cell=cells, wifi=wifis, ip=self.london_ip)
        self.check_stats(total=1, counter=[
            ('locate.query',
                ['key:key', 'country:xx', 'cell:one', 'wifi:one']),
        ])

    def test_many(self):
        cells = CellFactory.build_batch(2)
        wifis = WifiFactory.build_batch(3)

        self._make_query(cell=cells, wifi=wifis, ip=self.london_ip)
        self.check_stats(total=1, counter=[
            ('locate.query',
                ['key:key', 'country:xx', 'cell:many', 'wifi:many']),
        ])


class TestResultStats(QueryTest):

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
        api_key = ApiKeyFactory.build(shortname='key', log=False)
        self._make_query(Position(), api_key=api_key)
        self.check_stats(total=0)

    def test_country_api(self):
        self._make_query(Position(), api_type='country', ip=self.london_ip)
        self.check_stats(total=0)

    def test_none(self):
        self._make_query(
            Position(), ip=self.london_ip, fallback={'ipf': False})
        self.check_stats(total=0)

    def test_low_miss(self):
        self._make_query(Position(), ip=self.london_ip)
        self.check_stats(counter=[
            ('locate.result',
                ['key:key', 'country:xx', 'accuracy:low', 'status:miss']),
        ])

    def test_low_hit(self):
        self._make_query(Position(accuracy=60000.0), ip=self.london_ip)
        self.check_stats(counter=[
            ('locate.result',
                ['key:key', 'country:xx', 'accuracy:low', 'status:hit']),
        ])

    def test_medium_miss(self):
        cells = CellFactory.build_batch(1)
        self._make_query(Position(), cell=cells)
        self.check_stats(counter=[
            ('locate.result',
                ['key:key', 'country:none', 'accuracy:medium', 'status:miss']),
        ])

    def test_medium_miss_low(self):
        cells = CellFactory.build_batch(1)
        self._make_query(Position(accuracy=60000.0), cell=cells)
        self.check_stats(counter=[
            ('locate.result',
                ['key:key', 'country:none', 'accuracy:medium', 'status:miss']),
        ])

    def test_medium_hit(self):
        cells = CellFactory.build_batch(1)
        self._make_query(Position(accuracy=30000.0), cell=cells)
        self.check_stats(counter=[
            ('locate.result',
                ['key:key', 'country:none', 'accuracy:medium', 'status:hit']),
        ])

    def test_high_miss(self):
        wifis = WifiFactory.build_batch(2)
        self._make_query(Position(accuracy=1500.0), wifi=wifis)
        self.check_stats(counter=[
            ('locate.result',
                ['key:key', 'country:none', 'accuracy:high', 'status:miss']),
        ])

    def test_high_hit(self):
        wifis = WifiFactory.build_batch(2)
        self._make_query(Position(accuracy=1000.0), wifi=wifis)
        self.check_stats(counter=[
            ('locate.result',
                ['key:key', 'country:none', 'accuracy:high', 'status:hit']),
        ])

    def test_mixed_miss(self):
        wifis = WifiFactory.build_batch(2)
        self._make_query(Position(accuracy=1001.0),
                         wifi=wifis, ip=self.london_ip)
        self.check_stats(counter=[
            ('locate.result',
                ['key:key', 'country:xx', 'accuracy:high', 'status:miss']),
        ])

    def test_mixed_hit(self):
        cells = CellFactory.build_batch(2)
        self._make_query(Position(accuracy=500.0),
                         cell=cells, ip=self.london_ip)
        self.check_stats(counter=[
            ('locate.result',
                ['key:key', 'country:xx', 'accuracy:medium', 'status:hit']),
        ])


class TestSourceStats(QueryTest, ConnectionTestCase):

    def _make_query(self, source, result, api_key=None, api_type='locate',
                    cell=(), wifi=(), **kw):
        query = Query(
            api_key=api_key or self.api_key,
            api_type=api_type,
            cell=self.cell_model_query(cell),
            wifi=self.wifi_model_query(wifi),
            geoip_db=self.geoip_db,
            stats_client=self.stats_client,
            **kw)
        query.emit_source_stats(source, result)
        return query

    def test_high_hit(self):
        wifis = WifiFactory.build_batch(2)
        self._make_query(
            DataSource.internal, Position(accuracy=100.0), wifi=wifis)
        self.check_stats(counter=[
            # TODO
            # ('locate.source',
            #     ['key:key', 'country:none', 'source:internal',
            #      'accuracy:high', 'status:hit']),
        ])

    def test_high_miss(self):
        wifis = WifiFactory.build_batch(2)
        self._make_query(
            DataSource.ocid, Position(accuracy=10000.0), wifi=wifis)
        self.check_stats(counter=[
            # TODO
            # ('locate.source',
            #     ['key:key', 'country:none', 'source:ocid',
            #      'accuracy:high', 'status:miss']),
        ])
