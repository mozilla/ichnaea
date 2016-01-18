from ichnaea.api.locate.tests.base import (
    BaseLocateTest,
    CommonLocateErrorTest,
    CommonLocateTest,
)
from ichnaea.tests.base import AppTestCase
from ichnaea.tests.factories import (
    CellShardFactory,
    WifiShardFactory,
)


class RegionBase(BaseLocateTest, AppTestCase):

    url = '/v1/country'
    apikey_metrics = False
    metric_path = 'path:v1.country'
    metric_type = 'region'

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

        expected = super(RegionBase, self).check_model_response(
            response, model,
            region=region,
            fallback=fallback,
            expected_names=expected_names,
            **kw)

        data = response.json
        self.assertEqual(data['country_code'], expected['region'])
        if fallback is not None:
            self.assertEqual(data['fallback'], fallback)


class TestView(RegionBase, CommonLocateTest):

    track_connection_events = True

    def test_geoip(self):
        res = self._call(ip=self.test_ip)
        self.check_response(res, 'ok')
        self.assertEqual(res.headers['Access-Control-Allow-Origin'], '*')
        self.assertEqual(res.headers['Access-Control-Max-Age'], '2592000')
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
        cell = CellShardFactory.create(mcc=235)
        query = self.model_query(cells=[cell])
        res = self._call(body=query)
        self.check_model_response(res, cell, region='GB')
        self.check_db_calls(rw=0, ro=0)

    def test_cell_ambiguous(self):
        # cell with ambiguous mcc to region mapping
        cell = CellShardFactory.create(mcc=234)
        query = self.model_query(cells=[cell])
        res = self._call(body=query)
        self.check_model_response(res, cell, region='GB')
        self.check_db_calls(rw=0, ro=1)

    def test_cell_geoip_match(self):
        cell = CellShardFactory.create(mcc=234)
        query = self.model_query(cells=[cell])
        res = self._call(body=query, ip=self.test_ip)
        self.check_model_response(res, cell, region='GB')
        self.check_db_calls(rw=0, ro=1)

    def test_cell_geoip_mismatch(self):
        # UK GeoIP with ambiguous US mcc
        uk_cell = CellShardFactory.build(mcc=234)
        us_cell = CellShardFactory.create(mcc=310)
        query = self.model_query(cells=[us_cell])
        res = self._call(body=query, ip=self.test_ip)
        self.check_model_response(res, uk_cell, region='GB', fallback='ipf')
        self.check_db_calls(rw=0, ro=1)

    def test_cell_over_geoip(self):
        # UK GeoIP with single DE cell
        cell = CellShardFactory.create(mcc=262)
        query = self.model_query(cells=[cell])
        res = self._call(body=query, ip=self.test_ip)
        self.check_model_response(res, cell, region='DE')
        self.check_db_calls(rw=0, ro=0)

    def test_cells_over_geoip(self):
        # UK GeoIP with multiple US cells
        us_cell1 = CellShardFactory.create(mcc=310, samples=100)
        us_cell2 = CellShardFactory.create(mcc=311, samples=100)
        query = self.model_query(cells=[us_cell1, us_cell2])
        res = self._call(body=query, ip=self.test_ip)
        self.check_model_response(res, us_cell1, region='US')
        self.check_db_calls(rw=0, ro=1)

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


class TestError(RegionBase, CommonLocateErrorTest):

    @property
    def ip_response(self):
        return {
            'country_code': 'GB',
            'country_name': 'United Kingdom',
            # actually a mcc based response
            # 'fallback': 'ipf',
        }

    def test_database_error(self):
        super(TestError, self).test_database_error(db_errors=1)
