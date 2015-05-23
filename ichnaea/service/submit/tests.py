from datetime import datetime

from pyramid.testing import DummyRequest
import pytz

from ichnaea.models import Radio
from ichnaea.customjson import dumps
from ichnaea.service.error import preprocess_request
from ichnaea.service.submit.schema import (
    ReportSchema,
    SubmitSchema,
)
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
        schema = ReportSchema()
        request = self._make_request('{}')
        data, errors = preprocess_request(request, schema, response=None)
        self.assertEquals(data['lat'], None)
        self.assertEquals(data['lon'], None)
        self.assertFalse(errors)

    def test_empty_wifi_entry(self):
        schema = ReportSchema()
        wifi = WifiFactory.build()
        request = self._make_request(
            '{"lat": %s, "lon": %s, "wifi": [{}]}' % (wifi.lat, wifi.lon))
        data, errors = preprocess_request(request, schema, response=None)
        self.assertTrue(errors)


class TestSubmitSchema(SchemaTest):

    def test_empty(self):
        schema = SubmitSchema()
        request = self._make_request('{}')
        data, errors = preprocess_request(request, schema, response=None)
        self.assertTrue(errors)

    def test_minimal(self):
        schema = SubmitSchema()
        wifi = WifiFactory.build()
        request = self._make_request(
            '{"items": [{"lat": %s, "lon": %s}]}' % (wifi.lat, wifi.lon))
        data, errors = preprocess_request(request, schema, response=None)
        self.assertFalse(errors)
        self.assertTrue('items' in data)
        self.assertEqual(len(data['items']), 1)


class SubmitTest(CeleryAppTestCase):

    def setUp(self):
        super(SubmitTest, self).setUp()
        self.queue = self.celery_app.export_queues['internal']

    def _post(self, items, api_key=None, status=204, **kw):
        url = '/v1/submit'
        if api_key:
            url += '?key=%s' % api_key
        return self.app.post_json(url, {'items': items}, status=status, **kw)


class TestSubmit(SubmitTest):

    def test_ok_cell(self):
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
        self.assertEqual(res.body, '')

        self.assertEqual(self.queue.size(self.queue.queue_key()), 1)
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

    def test_ok_wifi(self):
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

        self.assertEqual(self.queue.size(self.queue.queue_key()), 1)
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
        self.assertEqual(self.queue.size(self.queue.queue_key()), batch)

    def test_gzip(self):
        wifi = WifiFactory.build()
        data = {'items': [{'lat': wifi.lat,
                           'lon': wifi.lon,
                           'wifi': [{'key': wifi.key}]}]}
        body = util.encode_gzip(dumps(data))
        headers = {'Content-Encoding': 'gzip'}
        self.app.post(
            '/v1/submit?key=test', body, headers=headers,
            content_type='application/json', status=204)


class TestNickname(SubmitTest):

    nickname = 'World Tr\xc3\xa4veler'.decode('utf-8')
    email = 'world_tr\xc3\xa4veler@email.com'.decode('utf-8')

    def _post_one_wifi(self, nickname=None, email=None):
        wifi = WifiFactory.build()
        data = {'lat': wifi.lat, 'lon': wifi.lon, 'wifi': [{'key': wifi.key}]}
        headers = {}
        if nickname:
            headers['X-Nickname'] = nickname.encode('utf-8')
        if email:
            headers['X-Email'] = email.encode('utf-8')
        return self._post([data], headers=headers)

    def test_email_header_without_nickname(self):
        self._post_one_wifi(nickname=None, email=self.email)
        item = self.queue.dequeue(self.queue.queue_key())[0]
        self.assertEqual(item['metadata']['nickname'], None)
        self.assertEqual(item['metadata']['email'], self.email)

    def test_nickname_and_email_headers(self):
        self._post_one_wifi(nickname=self.nickname, email=self.email)
        item = self.queue.dequeue(self.queue.queue_key())[0]
        self.assertEqual(item['metadata']['nickname'], self.nickname)
        self.assertEqual(item['metadata']['email'], self.email)


class TestSubmitErrors(SubmitTest):

    def test_error(self):
        wifi = WifiFactory.build()
        res = self.app.post_json(
            '/v1/submit',
            [{'lat': wifi.lat, 'lon': wifi.lon, 'cell': []}],
            status=400)
        self.assertEqual(res.content_type, 'application/json')
        self.assertTrue('errors' in res.json)
        self.assertFalse('status' in res.json)
        self.check_raven(['JSONError'])

    def test_ignore_unknown_json_key(self):
        wifi = WifiFactory.build()
        self._post([{'lat': wifi.lat, 'lon': wifi.lon, 'foo': 1}])

    def test_error_no_mapping(self):
        res = self.app.post_json('/v1/submit', [1], status=400)
        self.assertTrue('errors' in res.json)

    def test_many_errors(self):
        wifi = WifiFactory.build()
        wifis = [{'wrong_key': 'ab'} for i in range(100)]
        res = self._post(
            [{'lat': wifi.lat, 'lon': wifi.lon, 'wifi': wifis}],
            status=400)
        self.assertEqual(res.content_type, 'application/json')
        self.assertTrue('errors' in res.json)
        self.assertTrue(len(res.json['errors']) < 10)
        self.check_raven(['JSONError'])

    def test_no_json(self):
        res = self.app.post('/v1/submit', '\xae', status=400)
        self.assertTrue('errors' in res.json)

    def test_missing_latlon(self):
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
        self.assertEqual(self.queue.size(self.queue.queue_key()), 2)

    def test_completely_empty(self):
        res = self.app.post_json('/v1/submit', None, status=400)
        self.assertEqual(res.content_type, 'application/json')
        self.assertTrue('errors' in res.json)
        self.assertTrue(len(res.json['errors']) == 0)


class TestStats(SubmitTest):

    def test_log_no_api_key(self):
        wifi = WifiFactory.build()
        self._post([{'lat': wifi.lat, 'lon': wifi.lon}])
        self.check_stats(counter=[
            ('submit.no_api_key', 1),
            ('submit.unknown_api_key', 0),
        ])

    def test_log_unknown_api_key(self):
        wifi = WifiFactory.build()
        self._post(
            [{'lat': wifi.lat, 'lon': wifi.lon}],
            api_key='invalidkey')
        self.check_stats(counter=[
            ('submit.no_api_key', 0),
            ('submit.unknown_api_key', 1),
            ('submit.api_key.invalidkey', 0),
        ])

    def test_stats(self):
        cell = CellFactory.build()
        wifi = WifiFactory.build()
        self._post([{
            'lat': cell.lat,
            'lon': cell.lon,
            'accuracy': 10,
            'altitude': 123,
            'altitude_accuracy': 7,
            'radio': cell.radio.name,
            'cell': [{
                'radio': cell.radio.name,
                'mcc': cell.mcc,
                'mnc': cell.mnc,
                'lac': cell.lac,
                'cid': cell.cid,
            }],
            'wifi': [{'key': wifi.key}],
        }], api_key='test')
        self.check_stats(
            counter=['items.api_log.test.uploaded.batches',
                     'items.uploaded.batches',
                     'submit.api_key.test',
                     'request.v1.submit.204'],
            timer=['items.api_log.test.uploaded.batch_size',
                   'items.uploaded.batch_size',
                   'request.v1.submit'],
        )


class TestRadio(SubmitTest):

    def _query(self):
        cell = CellFactory.build()
        query = {'lat': cell.lat, 'lon': cell.lon,
                 'cell': [{'mcc': cell.mcc, 'mnc': cell.mnc,
                           'lac': cell.lac, 'cid': cell.cid}]}
        return (cell, query)

    def test_missing_radio(self):
        cell, query = self._query()
        self._post([query])
        item = self.queue.dequeue(self.queue.queue_key())[0]
        self.assertFalse('radioType' in item['report']['cellTowers'])

    def test_missing_radio_in_observation(self):
        cell, query = self._query()
        query['radio'] = cell.radio.name
        self._post([query])
        item = self.queue.dequeue(self.queue.queue_key())[0]
        cells = item['report']['cellTowers']
        self.assertEqual(cells[0]['radioType'], cell.radio.name)

    def test_missing_radio_top_level(self):
        cell, query = self._query()
        query['cell'][0]['radio'] = cell.radio.name
        self._post([query])
        item = self.queue.dequeue(self.queue.queue_key())[0]
        cells = item['report']['cellTowers']
        self.assertEqual(cells[0]['radioType'], cell.radio.name)

    def test_invalid_radio(self):
        cell, query = self._query()
        query['cell'][0]['radio'] = '18'
        self._post([query])
        item = self.queue.dequeue(self.queue.queue_key())[0]
        cells = item['report']['cellTowers']
        self.assertEqual(cells[0]['radioType'], '18')
