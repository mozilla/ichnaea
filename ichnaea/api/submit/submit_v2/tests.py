import time

from ichnaea.models import Radio
from ichnaea.api.tests.base_submit import BaseSubmitTest
from ichnaea.tests.base import CeleryAppTestCase
from ichnaea.tests.factories import (
    CellFactory,
    WifiFactory,
)


class TestSubmitV2(BaseSubmitTest, CeleryAppTestCase):

    url = '/v1/geosubmit'
    metric = 'geosubmit'
    status = 200
    radio_id = 'radioType'
    cells_id = 'cellTowers'

    def _one_cell_query(self, radio=True):
        cell = CellFactory.build()
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

    def test_cell(self):
        now_ms = int(time.time() * 1000)
        cell = CellFactory.build(radio=Radio.wcdma)
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

        self._assert_queue_size(1)
        item = self.queue.dequeue(self.queue.queue_key())[0]
        self.assertEqual(item['metadata']['api_key'], 'test')
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
        wifi = WifiFactory.build()
        self._post([{
            'latitude': wifi.lat,
            'longitude': wifi.lon,
            'wifiAccessPoints': [{
                'macAddress': wifi.key,
                'age': 3,
                'channel': 5,
                'frequency': 2437,
                'radioType': '802.11n',
                'signalStrength': -90,
                'signalToNoiseRatio': 5,
                'xtra_field': 3,
            }]},
        ])

        self._assert_queue_size(1)
        item = self.queue.dequeue(self.queue.queue_key())[0]
        self.assertEqual(item['metadata']['api_key'], None)
        report = item['report']
        self.assertTrue('timestamp' in report)
        position = report['position']
        self.assertEqual(position['latitude'], wifi.lat)
        self.assertEqual(position['longitude'], wifi.lon)
        wifis = item['report']['wifiAccessPoints']
        self.assertEqual(len(wifis), 1)
        self.assertEqual(wifis[0]['macAddress'], wifi.key)
        self.assertEqual(wifis[0]['age'], 3),
        self.assertEqual(wifis[0]['channel'], 5),
        self.assertEqual(wifis[0]['frequency'], 2437),
        self.assertEqual(wifis[0]['radioType'], '802.11n')
        self.assertEqual(wifis[0]['signalStrength'], -90),
        self.assertEqual(wifis[0]['signalToNoiseRatio'], 5),
        self.assertFalse('xtra_field' in wifis[0])

    def test_batches(self):
        batch = 110
        wifis = WifiFactory.build_batch(batch)
        items = [{'latitude': wifi.lat,
                  'longitude': wifi.lon,
                  'wifiAccessPoints': [{'macAddress': wifi.key}]}
                 for wifi in wifis]

        # add a bad one, this will just be skipped
        items.append({'latitude': 10.0, 'longitude': 10.0, 'whatever': 'xx'})
        self._post(items)
        self._assert_queue_size(batch)

    def test_error(self):
        wifi = WifiFactory.build()
        self._post([{
            'latitude': wifi.lat,
            'longitude': wifi.lon,
            'wifiAccessPoints': [{
                'macAddress': 10,
            }],
        }], status=400)
        self._assert_queue_size(0)

    def test_error_invalid_float(self):
        wifi = WifiFactory.build()
        self._post([{
            'latitude': wifi.lat,
            'longitude': wifi.lon,
            'accuracy': float('+nan'),
            'altitude': float('-inf'),
            'wifiAccessPoints': [{
                'macAddress': wifi.key,
            }],
        }])

        self._assert_queue_size(1)
        item = self.queue.dequeue(self.queue.queue_key())[0]
        position = item['report']['position']
        self.assertFalse('accuracy' in position)
        self.assertFalse('altitude' in position)
