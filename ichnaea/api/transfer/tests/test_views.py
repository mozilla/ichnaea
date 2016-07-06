import mock
from redis import RedisError
from simplejson import dumps

from ichnaea.api.exceptions import (
    ParseError,
    ServiceUnavailable,
)
from ichnaea import util

_sentinel = object()


class TestView(object):

    url = '/v1/transfer'
    metric_path = 'path:v1.transfer'

    def queue(self, celery):
        return celery.data_queues['transfer_incoming']

    def _call(self, app, body=None, api_key=_sentinel,
              headers=None, method='post_json', status=200, **kw):
        url = self.url
        if api_key:
            if api_key is _sentinel:
                api_key = 'test'
            url += '?key=%s' % api_key
        call = getattr(app, method)
        if method in ('get', 'delete', 'head', 'options'):
            return call(url,
                        status=status,
                        headers=headers,
                        **kw)
        else:
            return call(url, body,
                        content_type='application/json',
                        status=status,
                        headers=headers,
                        **kw)

    def test_gzip(self, app, celery):
        data = {'items': [{}]}
        body = util.encode_gzip(dumps(data))
        headers = {'Content-Encoding': 'gzip'}
        res = self._call(app, body, headers=headers, method='post')
        assert res.headers['Access-Control-Allow-Origin'] == '*'
        assert res.headers['Access-Control-Max-Age'] == '2592000'
        assert self.queue(celery).size() == 0

    def test_malformed_gzip(self, app, celery):
        headers = {'Content-Encoding': 'gzip'}
        self._call(app, 'invalid',
                   headers=headers, method='post', status=400)
        assert self.queue(celery).size() == 0

    def test_error_get(self, app):
        res = self._call(app, method='get', status=400)
        assert res.json == ParseError.json_body()

    def test_error_empty_body(self, app):
        res = self._call(app, '', method='post', status=400)
        assert res.json == ParseError.json_body()

    def test_error_no_json(self, app):
        res = self._call(app, '\xae', method='post', status=400)
        assert res.json == ParseError.json_body()

    def test_error_no_mapping(self, app):
        res = self._call(app, [1], method='post_json', status=400)
        assert res.json == ParseError.json_body()

    def test_error_redis_failure(self, app, raven, stats):
        mock_queue = mock.Mock()
        mock_queue.side_effect = RedisError()

        with mock.patch('ichnaea.queue.DataQueue.enqueue', mock_queue):
            res = self._call(app, {'items': []}, status=503)
            assert res.json == ServiceUnavailable.json_body()

        assert mock_queue.called
        raven.check([('ServiceUnavailable', 1)])
        stats.check(counter=[
            ('request', [self.metric_path, 'method:post', 'status:503']),
        ])

    def test_options(self, app):
        res = self._call(app, method='options')
        assert res.headers['Access-Control-Allow-Origin'] == '*'
        assert res.headers['Access-Control-Max-Age'] == '2592000'
