from ichnaea.api.exceptions import (
    DailyLimitExceeded,
    InvalidAPIKey,
    LocationNotFound,
    ParseError,
)


class BaseLocateTest(object):

    url = None
    metric = None
    metric_url = None
    not_found = LocationNotFound

    @property
    def test_ip(self):
        # accesses data defined in GeoIPTestCase
        return self.geoip_data['London']['ip']

    @property
    def ip_response(self):  # pragma: no cover
        return {}

    def _call(self, body=None, api_key='test', ip=None, status=200,
              headers=None, method='post_json', **kw):
        url = self.url
        if api_key:
            url += '?key=%s' % api_key
        extra_environ = {}
        if ip is not None:
            extra_environ = {'HTTP_X_FORWARDED_FOR': ip}
        call = getattr(self.app, method)
        if method == 'get':
            return call(url,
                        extra_environ=extra_environ,
                        status=status,
                        headers=headers,
                        **kw)
        else:
            return call(url, body,
                        content_type='application/json',
                        extra_environ=extra_environ,
                        status=status,
                        headers=headers,
                        **kw)

    def check_response(self, response, status):
        self.assertEqual(response.content_type, 'application/json')
        self.assertEqual(response.charset, 'UTF-8')
        if status == 'ok':
            self.assertEqual(response.json, self.ip_response)
        elif status == 'invalid_key':
            self.assertEqual(response.json, InvalidAPIKey.json_body())
        elif status == 'not_found':
            self.assertEqual(response.json, self.not_found.json_body())
        elif status == 'parse_error':
            self.assertEqual(response.json, ParseError.json_body())
        elif status == 'limit_exceeded':
            self.assertEqual(response.json, DailyLimitExceeded.json_body())

    def check_model_response(self, response, model,
                             fallback=None, expected_names=(), **kw):
        expected = {}
        for name in ('lat', 'lon', 'accuracy'):
            if name in kw:
                expected[name] = kw[name]
            else:
                model_name = name
                if name == 'accuracy':
                    model_name = 'range'
                expected[name] = getattr(model, model_name)

        if fallback is not None:
            expected_names = set(expected_names).union(set(['fallback']))

        self.assertEqual(response.content_type, 'application/json')
        self.assertEqual(set(response.json.keys()), expected_names)

        return expected


class CommonLocateTest(BaseLocateTest):

    def test_get(self):
        res = self._call(body={}, ip=self.test_ip, method='get', status=200)
        self.check_response(res, 'ok')

    def test_empty_body(self):
        res = self._call('', ip=self.test_ip, method='post', status=200)
        self.check_response(res, 'ok')

    def test_empty_json(self):
        res = self._call({}, ip=self.test_ip, status=200)
        self.check_response(res, 'ok')

        if self.metric_url:
            self.check_stats(
                timer=[(self.metric_url, 1)],
                counter=[(self.metric + '.api_key.test', 1),
                         (self.metric + '.geoip_hit', 1),
                         (self.metric_url + '.200', 1),
                         (self.metric + '.geoip_city_found', 1),
                         (self.metric + '.api_log.test.geoip_hit', 1)],
            )

    def test_error_no_json(self):
        res = self._call('\xae', method='post', status=400)
        self.check_response(res, 'parse_error')
        if self.metric:
            self.check_stats(counter=[self.metric + '.api_key.test'])

    def test_error_no_mapping(self):
        res = self._call([1], status=400)
        self.check_response(res, 'parse_error')

    def test_error_unknown_key(self):
        res = self._call({'foo': 0}, ip=self.test_ip, status=200)
        self.check_response(res, 'ok')

    def test_no_api_key(self, status=400, response='invalid_key'):
        res = self._call({}, api_key=None, ip=self.test_ip, status=status)
        self.check_response(res, response)
        if self.metric:
            self.check_stats(counter=[self.metric + '.no_api_key'])

    def test_unknown_api_key(self, status=400, response='invalid_key'):
        res = self._call({}, api_key='invalid', ip=self.test_ip, status=status)
        self.check_response(res, response)
        if self.metric:
            self.check_stats(counter=[self.metric + '.unknown_api_key'])
