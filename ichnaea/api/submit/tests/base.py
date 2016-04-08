import mock
from redis import RedisError
from simplejson import dumps

from ichnaea.api.exceptions import (
    ParseError,
    ServiceUnavailable,
)
from ichnaea.models import Radio
from ichnaea import util


class BaseSubmitTest(object):

    url = None
    metric_path = None
    metric_type = 'submit'
    status = None

    def setUp(self):
        super(BaseSubmitTest, self).setUp()
        self.queue = self.celery_app.data_queues['update_incoming']

    def _one_cell_query(self, radio=True):
        raise NotImplementedError()

    def _post(self, items, api_key=None, status=status, **kw):
        url = self.url
        if api_key:
            url += '?key=%s' % api_key
        extra = {'HTTP_X_FORWARDED_FOR': self.geoip_data['London']['ip']}
        result = self.app.post_json(
            url, {'items': items},
            status=status, extra_environ=extra, **kw)
        return result

    def _post_one_cell(self, status=status):
        cell, query = self._one_cell_query()
        return self._post([query], status=status)

    def test_gzip(self):
        cell, query = self._one_cell_query()
        data = {'items': [query]}
        body = util.encode_gzip(dumps(data))
        headers = {'Content-Encoding': 'gzip'}
        res = self.app.post(
            self.url, body, headers=headers,
            content_type='application/json', status=self.status)
        self.assertEqual(res.headers['Access-Control-Allow-Origin'], '*')
        self.assertEqual(res.headers['Access-Control-Max-Age'], '2592000')
        self.assertEqual(self.queue.size(), 1)

    def test_malformed_gzip(self):
        headers = {'Content-Encoding': 'gzip'}
        self.app.post(
            self.url, 'invalid', headers=headers,
            content_type='application/json', status=400)
        self.assertEqual(self.queue.size(), 0)

    def test_error_get(self):
        res = self.app.get(self.url, status=400)
        self.assertEqual(res.json, ParseError.json_body())
        self.check_raven([('ParseError', 1)])

    def test_error_empty_body(self):
        res = self.app.post(self.url, '', status=400)
        self.assertEqual(res.json, ParseError.json_body())
        self.check_raven([('ParseError', 1)])

    def test_error_empty_json(self):
        res = self.app.post_json(self.url, {}, status=400)
        self.assertEqual(res.json, ParseError.json_body())
        self.check_raven([('ParseError', 1)])

    def test_error_no_json(self):
        res = self.app.post(self.url, '\xae', status=400)
        self.assertEqual(res.json, ParseError.json_body())
        self.check_raven([('ParseError', 1)])

    def test_error_no_mapping(self):
        res = self.app.post_json(self.url, [1], status=400)
        self.assertEqual(res.json, ParseError.json_body())
        self.check_raven([('ParseError', 1)])

    def test_error_redis_failure(self):
        mock_queue = mock.Mock()
        mock_queue.side_effect = RedisError()

        with mock.patch('ichnaea.queue.DataQueue.enqueue', mock_queue):
            res = self._post_one_cell(status=503)
            self.assertEqual(res.json, ServiceUnavailable.json_body())

        self.assertTrue(mock_queue.called)
        self.check_stats(counter=[
            ('data.batch.upload', 0),
            ('request', [self.metric_path, 'method:post', 'status:503']),
        ])

    def test_log_api_key_none(self):
        cell, query = self._one_cell_query()
        self._post([query], api_key=None)
        self.check_stats(counter=[
            (self.metric_type + '.request', [self.metric_path, 'key:none']),
        ])
        self.assertEqual(self.redis_client.keys('apiuser:*'), [])

    def test_log_api_key_invalid(self):
        cell, query = self._one_cell_query()
        self._post([query], api_key='invalid_key')
        self.check_stats(counter=[
            (self.metric_type + '.request', [self.metric_path, 'key:none']),
        ])
        self.assertEqual(self.redis_client.keys('apiuser:*'), [])

    def test_log_api_key_unknown(self):
        cell, query = self._one_cell_query()
        self._post([query], api_key='abcdefg')
        self.check_stats(counter=[
            (self.metric_type + '.request', [self.metric_path, 'key:invalid']),
        ])
        self.assertEqual(self.redis_client.keys('apiuser:*'), [])

    def test_log_stats(self):
        cell, query = self._one_cell_query()
        self._post([query], api_key='test')
        self.check_stats(counter=[
            ('data.batch.upload', 1),
            ('data.batch.upload', ['key:test']),
            ('request', [self.metric_path, 'method:post',
                         'status:%s' % self.status]),
            (self.metric_type + '.request', [self.metric_path, 'key:test']),
        ], timer=[
            ('request', [self.metric_path, 'method:post']),
        ])
        today = util.utcnow().date()
        self.assertEqual(
            [k.decode('ascii') for k in self.redis_client.keys('apiuser:*')],
            ['apiuser:submit:test:%s' % today.strftime('%Y-%m-%d')])

    def test_options(self):
        res = self.app.options(self.url, status=200)
        self.assertEqual(res.headers['Access-Control-Allow-Origin'], '*')
        self.assertEqual(res.headers['Access-Control-Max-Age'], '2592000')

    def test_radio_duplicated(self):
        cell, query = self._one_cell_query(radio=False)
        query[self.radio_id] = Radio.gsm.name
        query[self.cells_id][0][self.radio_id] = Radio.lte.name
        self._post([query])
        item = self.queue.dequeue()[0]
        cells = item['report']['cellTowers']
        self.assertEqual(cells[0]['radioType'], Radio.lte.name)

    def test_radio_invalid(self):
        cell, query = self._one_cell_query(radio=False)
        query[self.cells_id][0][self.radio_id] = '18'
        self._post([query])
        item = self.queue.dequeue()[0]
        cells = item['report']['cellTowers']
        self.assertEqual(cells[0]['radioType'], '18')

    def test_radio_missing(self):
        cell, query = self._one_cell_query(radio=False)
        self._post([query])
        item = self.queue.dequeue()[0]
        self.assertFalse('radioType' in item['report']['cellTowers'])

    def test_radio_missing_in_observation(self):
        cell, query = self._one_cell_query(radio=False)
        query[self.radio_id] = cell.radio.name
        self._post([query])
        item = self.queue.dequeue()[0]
        cells = item['report']['cellTowers']
        self.assertEqual(cells[0]['radioType'], cell.radio.name)

    def test_radio_missing_top_level(self):
        cell, query = self._one_cell_query()
        self._post([query])
        item = self.queue.dequeue()[0]
        cells = item['report']['cellTowers']
        self.assertEqual(cells[0]['radioType'], cell.radio.name)
