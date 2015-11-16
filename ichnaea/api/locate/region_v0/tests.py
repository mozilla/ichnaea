from ichnaea.api.exceptions import (
    RegionNotFoundV0,
    RegionNotFoundV0JS,
)
from ichnaea.api.locate.tests.base import BaseLocateTest
from ichnaea.tests.base import AppTestCase


class RegionBase(BaseLocateTest, AppTestCase):

    apikey_metrics = False
    metric_type = 'region'
    track_connection_events = True

    def _call(self, body=None, api_key=None, ip=None, status=200,
              headers=None, method='post_json', **kw):
        # default api_key to None
        return super(RegionBase, self)._call(
            body=body, api_key=api_key, ip=ip, status=status,
            headers=headers, method=method, **kw)


class CommonRegionTests(object):

    def test_geoip(self):
        res = self._call(ip=self.test_ip)
        self.check_response(res, 'ok')
        self.check_db_calls(rw=0, ro=0)
        self.check_stats(counter=[
            ('request', [self.metric_path, 'method:post', 'status:200']),
        ], timer=[
            ('request', [self.metric_path, 'method:post']),
        ])

    def test_geoip_miss(self):
        res = self._call(ip='127.0.0.1', status=404)
        self.check_response(res, 'not_found')
        self.check_db_calls(rw=0, ro=0)
        self.check_stats(counter=[
            ('request', [self.metric_path, 'method:post', 'status:404']),
        ], timer=[
            ('request', [self.metric_path, 'method:post']),
        ])

    def test_get(self):
        res = self._call(ip=self.test_ip, method='get', status=200)
        self.check_response(res, 'ok')
        self.check_stats(counter=[
            ('request', [self.metric_path, 'method:get', 'status:200']),
        ], timer=[
            ('request', [self.metric_path, 'method:get']),
        ])

    def test_cache(self):
        res = self._call(ip=self.test_ip, method='get', status=200)
        cache = res.cache_control
        self.assertFalse(cache.public)
        self.assertTrue(cache.private)
        self.assertTrue(cache.proxy_revalidate)
        self.assertEqual(cache.max_age, 60)
        self.assertEqual(cache.s_max_age, 0)

    def test_api_key(self):
        res = self._call(ip=self.test_ip, api_key='test')
        self.check_response(res, 'ok')
        self.check_db_calls(rw=0, ro=0)
        # we don't log any additional API-key specific metrics
        self.check_stats(total=2)


class TestJSONView(CommonRegionTests, RegionBase):

    url = '/country.json'
    metric_path = 'path:country.json'
    not_found = RegionNotFoundV0

    @property
    def ip_response(self):
        return {
            'country_code': 'GB',
            'country_name': 'United Kingdom',
        }

    def check_response(self, response, status):
        self.assertEqual(response.content_type, 'application/json')
        self.assertEqual(response.charset, 'UTF-8')
        if status == 'ok':
            self.assertEqual(response.json, self.ip_response)
        elif status == 'not_found':
            self.assertEqual(response.json, self.not_found.json_body())


class TestJSView(CommonRegionTests, RegionBase):

    url = '/country.js'
    metric_path = 'path:country.js'
    not_found = RegionNotFoundV0JS

    @property
    def ip_response(self):
        return """\
function geoip_country_code() { return 'GB'; }
function geoip_country_name() { return 'United Kingdom'; }
"""

    def check_response(self, response, status):
        self.assertEqual(response.content_type, 'text/javascript')
        self.assertEqual(response.charset, 'UTF-8')
        if status == 'ok':
            self.assertEqual(response.text, self.ip_response)
        elif status == 'not_found':
            self.assertEqual(response.text, self.not_found().text)
