from datetime import datetime

import colander
from pyramid.testing import DummyRequest
import pytz

from ichnaea.api.exceptions import ParseError
from ichnaea.api.submit.submit_v1.schema import (
    ReportV1Schema,
    SubmitV1Schema,
)
from ichnaea.api.submit.tests.base import BaseSubmitTest
from ichnaea.models import Radio
from ichnaea.tests.base import (
    CeleryAppTestCase,
    TestCase,
)
from ichnaea.tests.factories import (
    CellFactory,
    WifiFactory,
)
from ichnaea import util


class SchemaTest(TestCase):

    def _make_request(self, body):
        request = DummyRequest()
        request.body = body
        return request


class TestReportSchema(SchemaTest):

    def test_empty(self):
        schema = ReportV1Schema()
        data = schema.deserialize({})
        self.assertFalse('lat' in data)
        self.assertFalse('lon' in data)

    def test_empty_wifi_entry(self):
        schema = ReportV1Schema()
        wifi = WifiFactory.build()
        schema.deserialize({'lat': wifi.lat, 'lon': wifi.lon, 'wifi': [{}]})


class TestSubmitSchema(SchemaTest):

    def test_empty(self):
        with self.assertRaises(colander.Invalid):
            schema = SubmitV1Schema()
            schema.deserialize({})

    def test_minimal(self):
        schema = SubmitV1Schema()
        wifi = WifiFactory.build()
        data = schema.deserialize(
            {'items': [{'lat': wifi.lat, 'lon': wifi.lon, 'wifi': [{}]}]})
        self.assertTrue('items' in data)
        self.assertEqual(len(data['items']), 1)


class TestView(BaseSubmitTest, CeleryAppTestCase):

    url = '/v1/submit'
    metric = 'submit'
    metric_url = 'request.v1.submit'
    status = 204
    radio_id = 'radio'
    cells_id = 'cell'

    def _one_cell_query(self, radio=True):
        cell = CellFactory.build()
        query = {'lat': cell.lat, 'lon': cell.lon,
                 'cell': [{'mcc': cell.mcc, 'mnc': cell.mnc,
                           'lac': cell.lac, 'cid': cell.cid}]}
        if radio:
            query['cell'][0]['radio'] = cell.radio.name
        return (cell, query)

    def test_cell(self):
        now = util.utcnow()
        today = now.replace(hour=0, minute=0, second=0)
        cell = CellFactory.build(radio=Radio.umts)
        res = self._post([{
            'lat': cell.lat,
            'lon': cell.lon,
            'time': today.strftime('%Y-%m-%d'),
            'accuracy': 10,
            'altitude': 123,
            'altitude_accuracy': 7,
            'radio': cell.radio.name,
            'cell': [{
                'radio': cell.radio.name, 'mcc': cell.mcc,
                'mnc': cell.mnc, 'lac': cell.lac, 'cid': cell.cid}],
        }], api_key='test')
        self.assertEqual(res.body, b'')

        self._assert_queue_size(1)
        item = self.queue.dequeue(self.queue.queue_key())[0]
        self.assertEqual(item['metadata']['api_key'], 'test')
        report = item['report']
        timestamp = datetime.utcfromtimestamp(report['timestamp'] / 1000.0)
        timestamp = timestamp.replace(microsecond=0, tzinfo=pytz.UTC)
        self.assertEqual(timestamp, today)
        position = report['position']
        self.assertEqual(position['latitude'], cell.lat)
        self.assertEqual(position['longitude'], cell.lon)
        self.assertEqual(position['accuracy'], 10)
        self.assertEqual(position['altitude'], 123)
        self.assertEqual(position['altitudeAccuracy'], 7)
        cells = report['cellTowers']
        self.assertEqual(cells[0]['radioType'], 'wcdma')
        self.assertEqual(cells[0]['mobileCountryCode'], cell.mcc)
        self.assertEqual(cells[0]['mobileNetworkCode'], cell.mnc)
        self.assertEqual(cells[0]['locationAreaCode'], cell.lac)
        self.assertEqual(cells[0]['cellId'], cell.cid)

    def test_wifi(self):
        wifi = WifiFactory.build()
        self._post([{
            'lat': wifi.lat,
            'lon': wifi.lon,
            'accuracy': 17,
            'wifi': [{'key': wifi.key.upper(),
                      'frequency': 2437,
                      'signal': -70,
                      'signalToNoiseRatio': 5,
                      }]
        }])

        self._assert_queue_size(1)
        item = self.queue.dequeue(self.queue.queue_key())[0]
        self.assertEqual(item['metadata']['api_key'], None)
        report = item['report']
        position = report['position']
        self.assertEqual(position['latitude'], wifi.lat)
        self.assertEqual(position['longitude'], wifi.lon)
        self.assertEqual(position['accuracy'], 17)
        self.assertFalse('altitude' in position)
        self.assertFalse('altitudeAccuracy' in position)
        wifis = report['wifiAccessPoints']
        self.assertEqual(wifis[0]['macAddress'], wifi.key.upper())
        self.assertFalse('channel' in wifis[0])
        self.assertEqual(wifis[0]['frequency'], 2437)
        self.assertEqual(wifis[0]['signalStrength'], -70)
        self.assertEqual(wifis[0]['signalToNoiseRatio'], 5)

    def test_batches(self):
        batch = 110
        wifis = WifiFactory.build_batch(batch)
        items = [{'lat': wifi.lat,
                  'lon': wifi.lon,
                  'wifi': [{'key': wifi.key}]}
                 for wifi in wifis]

        # add a bad one, this will just be skipped
        items.append({'lat': 10.0, 'lon': 10.0, 'whatever': 'xx'})
        self._post(items)
        self._assert_queue_size(batch)

    def test_error(self):
        wifi = WifiFactory.build()
        res = self.app.post_json(
            '/v1/submit',
            [{'lat': wifi.lat, 'lon': wifi.lon, 'cell': []}],
            status=400)
        self.assertEqual(res.json, ParseError.json_body())
        self.check_raven(['ParseError'])

    def test_error_missing_latlon(self):
        wifi = WifiFactory.build()
        self._post([
            {'lat': wifi.lat,
             'lon': wifi.lon,
             'accuracy': 17,
             'wifi': [{'key': wifi.key}],
             },
            {'wifi': [{'key': wifi.key}],
             'accuracy': 16},
        ])
        self._assert_queue_size(2)
