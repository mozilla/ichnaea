import time

from ichnaea.customjson import dumps
from ichnaea.models import Radio
from ichnaea.tests.base import CeleryAppTestCase
from ichnaea.tests.factories import (
    CellFactory,
    WifiFactory,
)
from ichnaea import util


class GeoSubmitTest(CeleryAppTestCase):

    def setUp(self):
        super(GeoSubmitTest, self).setUp()
        self.queue = self.celery_app.export_queues['internal']

    def _assert_queue_size(self, expected):
        self.assertEqual(self.queue.size(self.queue.queue_key()), expected)

    def _post(self, items, api_key='test', status=200, **kw):
        url = '/v1/geosubmit'
        if api_key:
            url += '?key=%s' % api_key
        return self.app.post_json(url, {'items': items}, status=status, **kw)

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


class TestGeoSubmit(GeoSubmitTest):

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
            'pressure': 1010,
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
        ])
        # check that we get an empty response
        self.assertEqual(response.content_type, 'application/json')
        self.assertEqual(response.json, {})

        self._assert_queue_size(1)
        item = self.queue.dequeue(self.queue.queue_key())[0]
        self.assertEqual(item['metadata']['api_key'], 'test')
        report = item['report']
        self.assertEqual(report['timestamp'], now_ms)
        self.assertFalse('xtra_field' in report)
        position = report['position']
        self.assertEqual(position['latitude'], cell.lat)
        self.assertEqual(position['longitude'], cell.lon)
        self.assertEqual(position['accuracy'], 12.4)
        self.assertEqual(position['age'], 1)
        self.assertEqual(position['altitude'], 100.1)
        self.assertEqual(position['altitudeAccuracy'], 23.7)
        self.assertEqual(position['carrier'], 'Some Carrier')
        self.assertEqual(position['heading'], 45.0)
        self.assertEqual(position['homeMobileCountryCode'], cell.mcc)
        self.assertEqual(position['homeMobileNetworkCode'], cell.mnc)
        self.assertEqual(position['pressure'], 1010)
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
        ], api_key=None)

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
        items.append({'lat': 10.0, 'lon': 10.0, 'whatever': 'xx'})
        self._post(items)
        self._assert_queue_size(batch)

    def test_gzip(self):
        cell, query = self._one_cell_query()
        data = {'items': [query]}
        body = util.encode_gzip(dumps(data))
        headers = {'Content-Encoding': 'gzip'}
        self.app.post(
            '/v1/geosubmit?key=test', body, headers=headers,
            content_type='application/json', status=200)
        self._assert_queue_size(1)


class TestNickname(GeoSubmitTest):

    nickname = 'World Tr\xc3\xa4veler'.decode('utf-8')
    email = 'world_tr\xc3\xa4veler@email.com'.decode('utf-8')

    def _post_one_cell(self, nickname=None, email=None):
        cell, query = self._one_cell_query()
        headers = {}
        if nickname:
            headers['X-Nickname'] = nickname.encode('utf-8')
        if email:
            headers['X-Email'] = email.encode('utf-8')
        return self._post([query], headers=headers)

    def test_email_header_without_nickname(self):
        self._post_one_cell(nickname=None, email=self.email)
        item = self.queue.dequeue(self.queue.queue_key())[0]
        self.assertEqual(item['metadata']['nickname'], None)
        self.assertEqual(item['metadata']['email'], self.email)

    def test_nickname_and_email_headers(self):
        self._post_one_cell(nickname=self.nickname, email=self.email)
        item = self.queue.dequeue(self.queue.queue_key())[0]
        self.assertEqual(item['metadata']['nickname'], self.nickname)
        self.assertEqual(item['metadata']['email'], self.email)


class GeoTestSubmitErrors(GeoSubmitTest):

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

    def test_invalid_float(self):
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


class TestStats(GeoSubmitTest):

    def test_log_no_api_key(self):
        cell, query = self._one_cell_query()
        self._post([query], api_key=None)
        self.check_stats(counter=[
            ('geosubmit.no_api_key', 1),
            ('geosubmit.unknown_api_key', 0),
        ])

    def test_log_unknown_api_key(self):
        cell, query = self._one_cell_query()
        self._post([query], api_key='invalidkey')
        self.check_stats(counter=[
            ('geosubmit.api_key.invalidkey', 0),
            ('geosubmit.no_api_key', 0),
            ('geosubmit.unknown_api_key', 1),
        ])

    def test_stats(self):
        cell, query = self._one_cell_query()
        self._post([query])
        self.check_stats(
            counter=['geosubmit.api_key.test',
                     'items.api_log.test.uploaded.batches',
                     'items.uploaded.batches',
                     'request.v1.geosubmit.200'],
            timer=['items.api_log.test.uploaded.batch_size',
                   'items.uploaded.batch_size',
                   'request.v1.geosubmit'])


class TestRadio(GeoSubmitTest):

    def test_duplicated_radio(self):
        cell, query = self._one_cell_query(radio=False)
        query['radioType'] = Radio.gsm.name
        query['cellTowers'][0]['radioType'] = Radio.lte.name
        self._post([query])
        item = self.queue.dequeue(self.queue.queue_key())[0]
        cells = item['report']['cellTowers']
        self.assertEqual(cells[0]['radioType'], Radio.lte.name)

    def test_missing_radio(self):
        cell, query = self._one_cell_query(radio=False)
        self._post([query])
        item = self.queue.dequeue(self.queue.queue_key())[0]
        self.assertFalse('radioType' in item['report']['cellTowers'])

    def test_missing_radio_in_observation(self):
        cell, query = self._one_cell_query(radio=False)
        query['radioType'] = cell.radio.name
        self._post([query])
        item = self.queue.dequeue(self.queue.queue_key())[0]
        cells = item['report']['cellTowers']
        self.assertEqual(cells[0]['radioType'], cell.radio.name)

    def test_missing_radio_top_level(self):
        cell, query = self._one_cell_query()
        self._post([query])
        item = self.queue.dequeue(self.queue.queue_key())[0]
        cells = item['report']['cellTowers']
        self.assertEqual(cells[0]['radioType'], cell.radio.name)

    def test_invalid_radio(self):
        cell, query = self._one_cell_query()
        query['cellTowers'][0]['radioType'] = '18'
        self._post([query])
        item = self.queue.dequeue(self.queue.queue_key())[0]
        cells = item['report']['cellTowers']
        self.assertEqual(cells[0]['radioType'], '18')
