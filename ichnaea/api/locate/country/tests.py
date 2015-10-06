from ichnaea.api.locate.tests.base import (
    BaseLocateTest,
    CommonLocateErrorTest,
    CommonLocateTest,
)
from ichnaea.tests.base import AppTestCase
from ichnaea.tests.factories import (
    CellFactory,
    WifiShardFactory,
)


class CountryBase(BaseLocateTest, AppTestCase):

    url = '/v1/country'
    apikey_metrics = False
    metric_path = 'path:v1.country'
    metric_type = 'country'

    @property
    def ip_response(self):
        return {
            'country_code': 'GB',
            'country_name': 'United Kingdom',
            'fallback': 'ipf',
        }

    def check_model_response(self, response, model,
                             region=None, fallback=None, **kw):
        expected_names = set(['country_code', 'country_name'])

        expected = super(CountryBase, self).check_model_response(
            response, model,
            region=region,
            fallback=fallback,
            expected_names=expected_names,
            **kw)

        data = response.json
        self.assertEqual(data['country_code'], expected['region'])
        if fallback is not None:
            self.assertEqual(data['fallback'], fallback)


class TestView(CountryBase, CommonLocateTest):

    track_connection_events = True

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

    def test_known_api_key(self):
        res = self._call(api_key='test', ip=self.test_ip)
        self.check_response(res, 'ok')
        self.check_db_calls(rw=0, ro=0)
        self.check_stats(counter=[
            ('request', [self.metric_path, 'method:post', 'status:200']),
            (self.metric_type + '.request', 0, [self.metric_path, 'key:test']),
        ], timer=[
            ('request', [self.metric_path, 'method:post']),
        ])

    def test_no_api_key(self):
        super(TestView, self).test_no_api_key(status=200, response='ok')
        self.check_db_calls(rw=0, ro=0)
        self.check_stats(counter=[
            (self.metric_type + '.request', 0, ['key:none']),
        ])

    def test_invalid_api_key(self):
        super(TestView, self).test_invalid_api_key(
            status=200, response='ok')
        self.check_db_calls(rw=0, ro=0)
        self.check_stats(counter=[
            (self.metric_type + '.request', 0,
                [self.metric_path, 'key:invalid']),
        ])

    def test_incomplete_request(self):
        res = self._call(body={'wifiAccessPoints': []}, ip=self.test_ip)
        self.check_response(res, 'ok')
        self.check_db_calls(rw=0, ro=0)

    def test_cell(self):
        # cell with unique mcc to region mapping
        cell = CellFactory.create(mcc=235)
        query = self.model_query(cells=[cell])
        res = self._call(body=query)
        self.check_model_response(res, cell, region='GB')
        self.check_db_calls(rw=0, ro=0)

    def test_cell_ambiguous(self):
        # cell with ambiguous mcc to region mapping
        cell = CellFactory.create(mcc=234)
        query = self.model_query(cells=[cell])
        res = self._call(body=query)
        self.check_model_response(res, cell, region='GB')
        self.check_db_calls(rw=0, ro=0)

    def test_cell_geoip_mismatch(self):
        # UK GeoIP with US mcc
        cell = CellFactory.create(mcc=310)
        query = self.model_query(cells=[cell])
        res = self._call(body=query, ip=self.test_ip)
        self.check_model_response(res, cell, region='US')
        self.check_db_calls(rw=0, ro=0)

    def test_wifi(self):
        wifis = WifiShardFactory.build_batch(2)
        query = self.model_query(wifis=wifis)
        res = self._call(
            body=query,
            ip='127.0.0.1',
            status=404)
        self.check_response(res, 'not_found')
        self.check_db_calls(rw=0, ro=0)

    def test_get(self):
        super(TestView, self).test_get()
        self.check_db_calls(rw=0, ro=0)


class TestError(CountryBase, CommonLocateErrorTest):

    @property
    def ip_response(self):
        return {
            'country_code': 'GB',
            'country_name': 'United Kingdom',
            # actually a mcc based response
            # 'fallback': 'ipf',
        }

    def test_database_error(self):
        super(TestError, self).test_database_error(db_errors=0)
