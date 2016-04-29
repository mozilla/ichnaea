import time

import colander

from ichnaea.models import Radio
from ichnaea.api.submit.schema_v1 import SUBMIT_V1_SCHEMA
from ichnaea.api.submit.tests.base import BaseSubmitTest
from ichnaea.tests.base import (
    CeleryAppTestCase,
    TestCase,
)
from ichnaea.tests.factories import (
    BlueShardFactory,
    CellShardFactory,
    WifiShardFactory,
)


class TestSubmitSchema(TestCase):

    schema = SUBMIT_V1_SCHEMA

    def test_empty(self):
        with self.assertRaises(colander.Invalid):
            self.schema.deserialize({})

    def test_timestamp(self):
        wifi = WifiShardFactory.build()

        data = self.schema.deserialize(
            {'items': [{'timestamp': 146 * 10 ** 10,
                        'wifiAccessPoints': [{'macAddress': wifi.mac}]}]})
        self.assertEqual(data['items'][0]['timestamp'], 146 * 10 ** 10)

        data = self.schema.deserialize(
            {'items': [{'timestamp': 146 * 10 ** 9,
                        'wifiAccessPoints': [{'macAddress': wifi.mac}]}]})
        # value was discarded and replaced by 'now'
        self.assertTrue(data['items'][0]['timestamp'] > 10 ** 12)


class TestView(BaseSubmitTest, CeleryAppTestCase):

    url = '/v1/geosubmit'
    metric_path = 'path:v1.geosubmit'
    status = 200
    radio_id = 'radioType'
    cells_id = 'cellTowers'

    def _one_cell_query(self, radio=True):
        cell = CellShardFactory.build()
        query = {
            'latitude': cell.lat,
            'longitude': cell.lon,
            'cellTowers': [{
                'mobileCountryCode': cell.mcc,
                'mobileNetworkCode': cell.mnc,
                'locationAreaCode': cell.lac,
                'cellId': cell.cid,
            }],
        }
        if radio:
            query['cellTowers'][0]['radioType'] = cell.radio.name
        return (cell, query)

    def test_blue(self):
        blue = BlueShardFactory.build()
        self._post([{
            'latitude': blue.lat,
            'longitude': blue.lon,
            'bluetoothBeacons': [{
                'macAddress': blue.mac,
                'age': 3,
                'signalStrength': -90,
                'name': 'my-beacon',
                'xtra_field': 3,
            }]},
        ])

        self.assertEqual(self.queue.size(), 1)
        item = self.queue.dequeue()[0]
        self.assertEqual(item['api_key'], None)
        report = item['report']
        self.assertTrue('timestamp' in report)
        position = report['position']
        self.assertEqual(position['latitude'], blue.lat)
        self.assertEqual(position['longitude'], blue.lon)
        blues = item['report']['bluetoothBeacons']
        self.assertEqual(len(blues), 1)
        self.assertEqual(blues[0]['macAddress'], blue.mac)
        self.assertEqual(blues[0]['age'], 3),
        self.assertEqual(blues[0]['signalStrength'], -90),
        self.assertEqual(blues[0]['name'], 'my-beacon'),
        self.assertFalse('xtra_field' in blues[0])

    def test_cell(self):
        now_ms = int(time.time() * 1000)
        cell = CellShardFactory.build(radio=Radio.wcdma)
        response = self._post([{
            'latitude': cell.lat,
            'longitude': cell.lon,
            'accuracy': 12.4,
            'age': 1,
            'altitude': 100.1,
            'altitudeAccuracy': 23.7,
            'carrier': 'Some Carrier',
            'heading': 45.0,
            'homeMobileCountryCode': cell.mcc,
            'homeMobileNetworkCode': cell.mnc,
            'pressure': 1013.25,
            'source': 'fused',
            'speed': 3.6,
            'timestamp': now_ms,
            'xtra_field': 1,
            'cellTowers': [{
                'radioType': 'umts',
                'mobileCountryCode': cell.mcc,
                'mobileNetworkCode': cell.mnc,
                'locationAreaCode': cell.lac,
                'cellId': cell.cid,
                'psc': cell.psc,
                'age': 3,
                'asu': 31,
                'serving': 1,
                'signalStrength': -51,
                'timingAdvance': 1,
                'xtra_field': 2,
            }]},
        ], api_key='test')
        # check that we get an empty response
        self.assertEqual(response.content_type, 'application/json')
        self.assertEqual(response.json, {})

        self.assertEqual(self.queue.size(), 1)
        item = self.queue.dequeue()[0]
        self.assertEqual(item['api_key'], 'test')
        report = item['report']
        self.assertEqual(report['timestamp'], now_ms)
        self.assertEqual(report['carrier'], 'Some Carrier')
        self.assertEqual(report['homeMobileCountryCode'], cell.mcc)
        self.assertEqual(report['homeMobileNetworkCode'], cell.mnc)
        self.assertFalse('xtra_field' in report)
        position = report['position']
        self.assertEqual(position['latitude'], cell.lat)
        self.assertEqual(position['longitude'], cell.lon)
        self.assertEqual(position['accuracy'], 12.4)
        self.assertEqual(position['age'], 1)
        self.assertEqual(position['altitude'], 100.1)
        self.assertEqual(position['altitudeAccuracy'], 23.7)
        self.assertEqual(position['heading'], 45.0)
        self.assertEqual(position['pressure'], 1013.25)
        self.assertEqual(position['source'], 'fused')
        self.assertEqual(position['speed'], 3.6)
        self.assertFalse('xtra_field' in position)
        cells = report['cellTowers']
        self.assertEqual(len(cells), 1)
        self.assertEqual(cells[0]['radioType'], 'wcdma')
        self.assertEqual(cells[0]['mobileCountryCode'], cell.mcc)
        self.assertEqual(cells[0]['mobileNetworkCode'], cell.mnc)
        self.assertEqual(cells[0]['locationAreaCode'], cell.lac)
        self.assertEqual(cells[0]['cellId'], cell.cid)
        self.assertEqual(cells[0]['primaryScramblingCode'], cell.psc)
        self.assertEqual(cells[0]['age'], 3)
        self.assertEqual(cells[0]['asu'], 31)
        self.assertEqual(cells[0]['serving'], 1)
        self.assertEqual(cells[0]['signalStrength'], -51)
        self.assertEqual(cells[0]['timingAdvance'], 1)
        self.assertFalse('xtra_field' in cells[0])

    def test_wifi(self):
        wifi = WifiShardFactory.build()
        self._post([{
            'latitude': wifi.lat,
            'longitude': wifi.lon,
            'wifiAccessPoints': [{
                'macAddress': wifi.mac,
                'age': 3,
                'channel': 5,
                'frequency': 2437,
                'radioType': '802.11n',
                'signalStrength': -90,
                'signalToNoiseRatio': 5,
                'ssid': 'my-wifi',
                'xtra_field': 3,
            }]},
        ])

        self.assertEqual(self.queue.size(), 1)
        item = self.queue.dequeue()[0]
        self.assertEqual(item['api_key'], None)
        report = item['report']
        self.assertTrue('timestamp' in report)
        position = report['position']
        self.assertEqual(position['latitude'], wifi.lat)
        self.assertEqual(position['longitude'], wifi.lon)
        wifis = item['report']['wifiAccessPoints']
        self.assertEqual(len(wifis), 1)
        self.assertEqual(wifis[0]['macAddress'], wifi.mac)
        self.assertEqual(wifis[0]['age'], 3),
        self.assertEqual(wifis[0]['channel'], 5),
        self.assertEqual(wifis[0]['frequency'], 2437),
        self.assertEqual(wifis[0]['radioType'], '802.11n')
        self.assertEqual(wifis[0]['signalStrength'], -90),
        self.assertEqual(wifis[0]['signalToNoiseRatio'], 5),
        self.assertEqual(wifis[0]['ssid'], 'my-wifi'),
        self.assertFalse('xtra_field' in wifis[0])

    def test_batches(self):
        batch = self.queue.batch + 10
        wifis = WifiShardFactory.build_batch(batch)
        items = [{'latitude': wifi.lat,
                  'longitude': wifi.lon,
                  'wifiAccessPoints': [{'macAddress': wifi.mac}]}
                 for wifi in wifis]

        # add a bad one, this will just be skipped
        items.append({'latitude': 10.0, 'longitude': 10.0, 'whatever': 'xx'})
        self._post(items)
        self.assertEqual(self.queue.size(), batch)

    def test_error(self):
        wifi = WifiShardFactory.build()
        self._post([{
            'latitude': wifi.lat,
            'longitude': wifi.lon,
            'wifiAccessPoints': [{
                'macAddress': 10,
            }],
        }], status=400)
        self.assertEqual(self.queue.size(), 0)

    def test_error_missing_latlon(self):
        wifi = WifiShardFactory.build()
        self._post([
            {'latitude': wifi.lat,
             'longitude': wifi.lon,
             'accuracy': 17.0,
             'wifiAccessPoints': [{'macAddress': wifi.mac}],
             },
            {'wifiAccessPoints': [{'macAddress': wifi.mac}],
             'accuracy': 16.0},
            {'wifiAccessPoints': [{'macAddress': wifi.mac}]},
        ])
        self.assertEqual(self.queue.size(), 3)

    def test_error_invalid_float(self):
        wifi = WifiShardFactory.build()
        self._post([{
            'latitude': wifi.lat,
            'longitude': wifi.lon,
            'accuracy': float('+nan'),
            'altitude': float('-inf'),
            'wifiAccessPoints': [{
                'macAddress': wifi.mac,
            }],
        }])

        self.assertEqual(self.queue.size(), 1)
        item = self.queue.dequeue()[0]
        position = item['report']['position']
        self.assertFalse('accuracy' in position)
        self.assertFalse('altitude' in position)
