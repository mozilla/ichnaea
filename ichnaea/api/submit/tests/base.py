from ichnaea.api.exceptions import ParseError
from ichnaea.customjson import dumps
from ichnaea.models import Radio
from ichnaea import util


class BaseSubmitTest(object):

    url = None
    metric = None
    status = None

    nickname = b'World Tr\xc3\xa4veler'.decode('utf-8')
    email = b'world_tr\xc3\xa4veler@email.com'.decode('utf-8')

    def setUp(self):
        super(BaseSubmitTest, self).setUp()
        self.queue = self.celery_app.export_queues['internal']

    def _assert_queue_size(self, expected):
        self.assertEqual(self.queue.size(self.queue.queue_key()), expected)

    def _one_cell_query(self, radio=True):  # pragma: no cover
        raise NotImplementedError()

    def _post(self, items, api_key=None, status=status, **kw):
        url = self.url
        if api_key:
            url += '?key=%s' % api_key
        return self.app.post_json(url, {'items': items}, status=status, **kw)

    def _post_one_cell(self, nickname=None, email=None):
        cell, query = self._one_cell_query()
        headers = {}
        if nickname:
            headers['X-Nickname'] = nickname.encode('utf-8')
        if email:
            headers['X-Email'] = email.encode('utf-8')
        return self._post([query], headers=headers)

    def test_gzip(self):
        cell, query = self._one_cell_query()
        data = {'items': [query]}
        body = util.encode_gzip(dumps(data))
        headers = {'Content-Encoding': 'gzip'}
        self.app.post(
            self.url, body, headers=headers,
            content_type='application/json', status=self.status)
        self._assert_queue_size(1)

    def test_malformed_gzip(self):
        headers = {'Content-Encoding': 'gzip'}
        self.app.post(
            self.url, 'invalid', headers=headers,
            content_type='application/json', status=400)
        self._assert_queue_size(0)

    def test_error_get(self):
        res = self.app.get(self.url, status=400)
        self.assertEqual(res.json, ParseError.json_body())

    def test_error_empty_body(self):
        res = self.app.post(self.url, '', status=400)
        self.assertEqual(res.json, ParseError.json_body())

    def test_error_empty_json(self):
        res = self.app.post_json(self.url, {}, status=400)
        self.assertEqual(res.json, ParseError.json_body())

    def test_error_no_json(self):
        res = self.app.post(self.url, '\xae', status=400)
        self.assertEqual(res.json, ParseError.json_body())

    def test_error_no_mapping(self):
        res = self.app.post_json(self.url, [1], status=400)
        self.assertEqual(res.json, ParseError.json_body())

    def test_headers_email_without_nickname(self):
        self._post_one_cell(nickname=None, email=self.email)
        item = self.queue.dequeue(self.queue.queue_key())[0]
        self.assertEqual(item['metadata']['nickname'], None)
        self.assertEqual(item['metadata']['email'], self.email)

    def test_headers_nickname_and_email(self):
        self._post_one_cell(nickname=self.nickname, email=self.email)
        item = self.queue.dequeue(self.queue.queue_key())[0]
        self.assertEqual(item['metadata']['nickname'], self.nickname)
        self.assertEqual(item['metadata']['email'], self.email)

    def test_log_api_key_none(self):
        cell, query = self._one_cell_query()
        self._post([query], api_key=None)
        self.check_stats(counter=[
            (self.metric + '.no_api_key', 1),
            (self.metric + '.unknown_api_key', 0),
        ])

    def test_log_api_key_unknown(self):
        cell, query = self._one_cell_query()
        self._post([query], api_key='invalidkey')
        self.check_stats(counter=[
            (self.metric + '.api_key.invalidkey', 0),
            (self.metric + '.no_api_key', 0),
            (self.metric + '.unknown_api_key', 1),
        ])

    def test_log_stats(self):
        cell, query = self._one_cell_query()
        self._post([query], api_key='test')
        self.check_stats(
            counter=['items.api_log.test.uploaded.batches',
                     'items.uploaded.batches',
                     self.metric + '.api_key.test',
                     'request%s.%s' % (self.url.replace('/', '.'),
                                       self.status)],
            timer=['items.api_log.test.uploaded.batch_size',
                   'items.uploaded.batch_size',
                   'request' + self.url.replace('/', '.')])

    def test_radio_duplicated(self):
        cell, query = self._one_cell_query(radio=False)
        query[self.radio_id] = Radio.gsm.name
        query[self.cells_id][0][self.radio_id] = Radio.lte.name
        self._post([query])
        item = self.queue.dequeue(self.queue.queue_key())[0]
        cells = item['report']['cellTowers']
        self.assertEqual(cells[0]['radioType'], Radio.lte.name)

    def test_radio_invalid(self):
        cell, query = self._one_cell_query(radio=False)
        query[self.cells_id][0][self.radio_id] = '18'
        self._post([query])
        item = self.queue.dequeue(self.queue.queue_key())[0]
        cells = item['report']['cellTowers']
        self.assertEqual(cells[0]['radioType'], '18')

    def test_radio_missing(self):
        cell, query = self._one_cell_query(radio=False)
        self._post([query])
        item = self.queue.dequeue(self.queue.queue_key())[0]
        self.assertFalse('radioType' in item['report']['cellTowers'])

    def test_radio_missing_in_observation(self):
        cell, query = self._one_cell_query(radio=False)
        query[self.radio_id] = cell.radio.name
        self._post([query])
        item = self.queue.dequeue(self.queue.queue_key())[0]
        cells = item['report']['cellTowers']
        self.assertEqual(cells[0]['radioType'], cell.radio.name)

    def test_radio_missing_top_level(self):
        cell, query = self._one_cell_query()
        self._post([query])
        item = self.queue.dequeue(self.queue.queue_key())[0]
        cells = item['report']['cellTowers']
        self.assertEqual(cells[0]['radioType'], cell.radio.name)
