from datetime import datetime

import colander
import pytz

from ichnaea.api.exceptions import ParseError
from ichnaea.api.submit.schema_v0 import SUBMIT_V0_SCHEMA
from ichnaea.api.submit.tests.base import BaseSubmitTest
from ichnaea.models import Radio
from ichnaea.tests.base import (
    CeleryAppTestCase,
    TestCase,
)
from ichnaea.tests.factories import (
    BlueShardFactory,
    CellShardFactory,
    WifiShardFactory,
)
from ichnaea import util


class TestSubmitSchema(TestCase):

    schema = SUBMIT_V0_SCHEMA

    def test_empty(self):
        with self.assertRaises(colander.Invalid):
            self.schema.deserialize({})

    def test_empty_blue_entry(self):
        blue = BlueShardFactory.build()
        data = self.schema.deserialize({'items': [
            {'lat': blue.lat, 'lon': blue.lon, 'blue': [{}]},
        ]})
        self.assertEqual(data, {'items': []})

    def test_empty_wifi_entry(self):
        wifi = WifiShardFactory.build()
        data = self.schema.deserialize({'items': [
            {'lat': wifi.lat, 'lon': wifi.lon, 'wifi': [{}]},
        ]})
        self.assertEqual(data, {'items': []})

    def test_minimal(self):
        wifi = WifiShardFactory.build()
        data = self.schema.deserialize(
            {'items': [{'lat': wifi.lat, 'lon': wifi.lon,
                        'wifi': [{'key': 'ab'}]}]})
        self.assertTrue('items' in data)
        self.assertEqual(len(data['items']), 1)

    def test_timestamp(self):
        wifi = WifiShardFactory.build()

        data = self.schema.deserialize(
            {'items': [{'time': '2016-04-07T03:33:20',
                        'wifi': [{'key': wifi.mac}]}]})
        self.assertEqual(data['items'][0]['timestamp'], 1460000000000.0)

        data = self.schema.deserialize(
            {'items': [{'time': '1710-02-28',
                        'wifi': [{'key': wifi.mac}]}]})
        # 1710 was discarded and replaced by 'now'
        self.assertTrue(data['items'][0]['timestamp'] > 0.0)


class TestView(BaseSubmitTest, CeleryAppTestCase):

    url = '/v1/submit'
    metric_path = 'path:v1.submit'
    status = 204
    radio_id = 'radio'
    cells_id = 'cell'

    def _one_cell_query(self, radio=True):
        cell = CellShardFactory.build()
        query = {'lat': cell.lat, 'lon': cell.lon,
                 'cell': [{'mcc': cell.mcc, 'mnc': cell.mnc,
                           'lac': cell.lac, 'cid': cell.cid}]}
        if radio:
            query['cell'][0]['radio'] = cell.radio.name
        return (cell, query)

    def test_blue(self):
        blue = BlueShardFactory.build()
        res = self._post([{
            'lat': blue.lat,
            'lon': blue.lon,
            'blue': [{
                'key': blue.mac,
                'age': 3000,
                'name': 'beacon',
                'signal': -101,
            }]},
        ])
        self.assertEqual(res.body, b'')

        self._assert_queue_size(1)
        item = self.queue.dequeue(self.queue.queue_key())[0]
        self.assertEqual(item['api_key'], None)
        report = item['report']
        position = report['position']
        self.assertEqual(position['latitude'], blue.lat)
        self.assertEqual(position['longitude'], blue.lon)
        blues = item['report']['bluetoothBeacons']
        self.assertEqual(len(blues), 1)
        self.assertEqual(blues[0]['macAddress'], blue.mac)
        self.assertEqual(blues[0]['age'], 3000),
        self.assertEqual(blues[0]['name'], 'beacon'),
        self.assertEqual(blues[0]['signalStrength'], -101),

    def test_cell(self):
        now = util.utcnow()
        today = now.replace(hour=0, minute=0, second=0)
        cell = CellShardFactory.build(radio=Radio.umts)
        res = self._post([{
            'lat': cell.lat,
            'lon': cell.lon,
            'time': today.strftime('%Y-%m-%d'),
            'accuracy': 10.6,
            'altitude': 123.1,
            'altitude_accuracy': 7.0,
            'heading': 45.2,
            'pressure': 1020.23,
            'speed': 3.6,
            'radio': cell.radio.name,
            'cell': [{
                'radio': 'umts', 'mcc': cell.mcc,
                'mnc': cell.mnc, 'lac': cell.lac, 'cid': cell.cid,
                'age': 1000, 'asu': 3, 'psc': 7, 'serving': 1,
                'signal': -85, 'ta': 2}],
        }], api_key='test')
        self.assertEqual(res.body, b'')

        self._assert_queue_size(1)
        item = self.queue.dequeue(self.queue.queue_key())[0]
        self.assertEqual(item['api_key'], 'test')
        report = item['report']
        timestamp = datetime.utcfromtimestamp(report['timestamp'] / 1000.0)
        timestamp = timestamp.replace(microsecond=0, tzinfo=pytz.UTC)
        self.assertEqual(timestamp, today)
        position = report['position']
        self.assertAlmostEqual(position['latitude'], cell.lat)
        self.assertAlmostEqual(position['longitude'], cell.lon)
        self.assertAlmostEqual(position['accuracy'], 10.6)
        self.assertAlmostEqual(position['altitude'], 123.1)
        self.assertAlmostEqual(position['altitudeAccuracy'], 7.0)
        self.assertAlmostEqual(position['heading'], 45.2)
        self.assertAlmostEqual(position['pressure'], 1020.23)
        self.assertAlmostEqual(position['speed'], 3.6)
        cells = report['cellTowers']
        self.assertEqual(cells[0]['radioType'], 'wcdma')
        self.assertEqual(cells[0]['mobileCountryCode'], cell.mcc)
        self.assertEqual(cells[0]['mobileNetworkCode'], cell.mnc)
        self.assertEqual(cells[0]['locationAreaCode'], cell.lac)
        self.assertEqual(cells[0]['cellId'], cell.cid)
        self.assertEqual(cells[0]['age'], 1000)
        self.assertEqual(cells[0]['asu'], 3)
        self.assertEqual(cells[0]['primaryScramblingCode'], 7)
        self.assertEqual(cells[0]['serving'], 1)
        self.assertEqual(cells[0]['signalStrength'], -85)
        self.assertEqual(cells[0]['timingAdvance'], 2)

    def test_wifi(self):
        wifi = WifiShardFactory.build()
        self._post([{
            'lat': wifi.lat,
            'lon': wifi.lon,
            'accuracy': 17.1,
            'wifi': [{'key': wifi.mac.upper(),
                      'age': 2500,
                      'frequency': 2437,
                      'signal': -70,
                      'signalToNoiseRatio': 5,
                      'ssid': 'my-wifi',
                      }]
        }])

        self._assert_queue_size(1)
        item = self.queue.dequeue(self.queue.queue_key())[0]
        self.assertEqual(item['api_key'], None)
        report = item['report']
        position = report['position']
        self.assertEqual(position['latitude'], wifi.lat)
        self.assertEqual(position['longitude'], wifi.lon)
        self.assertEqual(position['accuracy'], 17.1)
        self.assertFalse('altitude' in position)
        self.assertFalse('altitudeAccuracy' in position)
        wifis = report['wifiAccessPoints']
        self.assertEqual(wifis[0]['macAddress'], wifi.mac.upper())
        self.assertEqual(wifis[0]['age'], 2500)
        self.assertFalse('channel' in wifis[0])
        self.assertEqual(wifis[0]['frequency'], 2437)
        self.assertEqual(wifis[0]['signalStrength'], -70)
        self.assertEqual(wifis[0]['signalToNoiseRatio'], 5)
        self.assertEqual(wifis[0]['ssid'], 'my-wifi')

    def test_batches(self):
        batch = 110
        wifis = WifiShardFactory.build_batch(batch)
        items = [{'lat': wifi.lat,
                  'lon': wifi.lon,
                  'wifi': [{'key': wifi.mac}]}
                 for wifi in wifis]

        # add a bad one, this will just be skipped
        items.append({'lat': 10.0, 'lon': 10.0, 'whatever': 'xx'})
        self._post(items)
        self._assert_queue_size(batch)

    def test_error(self):
        wifi = WifiShardFactory.build()
        res = self.app.post_json(
            '/v1/submit',
            [{'lat': wifi.lat, 'lon': wifi.lon, 'cell': []}],
            status=400)
        self.assertEqual(res.json, ParseError.json_body())
        self.check_raven(['ParseError'])

    def test_error_missing_latlon(self):
        wifi = WifiShardFactory.build()
        self._post([
            {'lat': wifi.lat,
             'lon': wifi.lon,
             'accuracy': 17.0,
             'wifi': [{'key': wifi.mac}],
             },
            {'wifi': [{'key': wifi.mac}],
             'accuracy': 16.0},
        ])
        self._assert_queue_size(2)
