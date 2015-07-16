from ichnaea.api.locate.query import Query
from ichnaea.tests.base import ConnectionTestCase
from ichnaea.tests.factories import (
    CellFactory,
    WifiFactory,
)


class TestQuery(ConnectionTestCase):

    def cell_model_query(self, cells):
        query = []
        for cell in cells:
            query.append({
                'radio': cell.radio.name,
                'mcc': cell.mcc,
                'mnc': cell.mnc,
                'lac': cell.lac,
                'cid': cell.cid,
                'psc': cell.psc,
                'signal': -90,
                'ta': 1,
            })
        return query

    def test_empty(self):
        query = Query()
        self.assertEqual(query.fallbacks, {})
        self.assertEqual(query.geoip, None)
        self.assertEqual(query.cell, [])
        self.assertEqual(query.cell_area, [])
        self.assertEqual(query.wifi, [])

    def test_fallbacks(self):
        query = Query(fallbacks={'ipf': False})
        self.assertEqual(query.fallbacks, {'ipf': False})

    def test_geoip(self):
        london_ip = self.geoip_data['London']['ip']
        query = Query(geoip=london_ip)
        self.assertEqual(query.geoip, london_ip)

    def test_geoip_malformed(self):
        query = Query(geoip='127.0.0.0.0.1')
        self.assertEqual(query.geoip, None)

    def test_cell(self):
        cell = CellFactory.build()
        cell_query = self.cell_model_query([cell])
        query = Query(cell=cell_query)

        self.assertEqual(len(query.cell), 1)
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

    def test_cell_area_duplicated(self):
        cell = CellFactory.build()
        cell_query = self.cell_model_query([cell, cell, cell])
        cell_query[1]['cid'] += 2
        cell_query[2]['cid'] += 1
        query = Query(cell=cell_query)
        self.assertEqual(len(query.cell), 3)
        self.assertEqual(len(query.cell_area), 1)

    def test_wifi(self):
        wifis = WifiFactory.build_batch(2)
        wifi_query = []
        wifi_keys = []
        for wifi in wifis:
            wifi_keys.append(wifi.key)
            wifi_query.append({
                'key': wifi.key,
                'signal': -85,
                'channel': 11,
            })
        query = Query(wifi=wifi_query)
        self.assertEqual(len(query.wifi), 2)

        for wifi in query.wifi:
            self.assertEqual(wifi.signal, -85)
            self.assertEqual(wifi.channel, 11)
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
