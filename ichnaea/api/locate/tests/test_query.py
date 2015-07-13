from ichnaea.api.locate.query import Query
from ichnaea.tests.base import ConnectionTestCase
from ichnaea.tests.factories import (
    CellFactory,
    WifiFactory,
)


class TestQuery(ConnectionTestCase):

    def test_empty(self):
        query = Query()
        self.assertEqual(query.cell, [])
        self.assertEqual(query.cell_area, [])
        self.assertEqual(query.geoip, None)
        self.assertEqual(query.wifi, [])

    def test_cell(self):
        cell = CellFactory.build()
        cell_query = {
            'radio': cell.radio.name,
            'mcc': cell.mcc,
            'mnc': cell.mnc,
            'lac': cell.lac,
            'cid': cell.cid,
            'psc': cell.psc,
            'signal': -90,
            'ta': 1,
        }
        query = Query(cell=[cell_query])

        self.assertEqual(len(query.cell), 1)
        query_cell = query.cell[0]
        for key, value in cell_query.items():
            if key == 'radio':
                self.assertEqual(query_cell[key], cell.radio)
            else:
                self.assertEqual(query_cell[key], value)

        self.assertEqual(len(query.cell_area), 1)
        query_area = query.cell_area[0]
        for key, value in cell_query.items():
            if key == 'radio':
                self.assertEqual(query_area[key], cell.radio)
            elif key in ('cid', 'psc'):
                pass
            else:
                self.assertEqual(query_area[key], value)

    def test_cell_malformed(self):
        query = Query(cell=[{'radio': 'foo', 'mcc': 'ab'}])
        self.assertEqual(len(query.cell), 0)

    def test_geoip(self):
        london_ip = self.geoip_data['London']['ip']
        query = Query(geoip=london_ip)
        self.assertEqual(query.geoip, london_ip)

    def test_geoip_malformed(self):
        query = Query(geoip='127.0.0.0.0.1')
        self.assertEqual(query.geoip, None)

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
            self.assertEqual(wifi['signal'], -85)
            self.assertEqual(wifi['channel'], 11)
            self.assertTrue(wifi['key'] in wifi_keys)

    def test_wifi_single(self):
        wifi = WifiFactory.build()
        wifi_query = {'key': wifi.key}
        query = Query(wifi=[wifi_query])
        self.assertEqual(len(query.wifi), 0)

    def test_wifi_malformed(self):
        wifi = WifiFactory.build()
        wifi_query = {'key': wifi.key}
        query = Query(wifi=[wifi_query, {'key': 'foo'}])
        self.assertEqual(len(query.wifi), 0)
