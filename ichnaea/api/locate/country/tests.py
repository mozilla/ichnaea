from ichnaea.api.locate.tests.base import (
    BaseLocateTest,
    CommonLocateErrorTest,
    CommonLocateTest,
)
from ichnaea.tests.base import AppTestCase
from ichnaea.tests.factories import (
    CellFactory,
    WifiFactory,
)


class CountryBase(BaseLocateTest, AppTestCase):

    url = '/v1/country'
    apikey_metrics = False
    metric = 'country'
    metric_url = 'request.v1.country'

    @property
    def ip_response(self):
        return {
            'country_code': 'GB',
            'country_name': 'United Kingdom',
            'fallback': 'ipf',
        }

    def check_model_response(self, response, model,
                             country=None, fallback=None, **kw):
        expected_names = set(['country_code', 'country_name'])

        expected = super(CountryBase, self).check_model_response(
            response, model,
            country=country,
            fallback=fallback,
            expected_names=expected_names,
            **kw)

        data = response.json
        self.assertEqual(data['country_code'], expected['country'])
        if fallback is not None:
            self.assertEqual(data['fallback'], fallback)


class TestView(CountryBase, CommonLocateTest):

    track_connection_events = True

    def test_geoip(self):
        res = self._call(ip=self.test_ip)
        self.check_response(res, 'ok')
        self.check_db_calls(rw=0, ro=0)
        self.check_stats(
            counter=[self.metric_url + '.200'],
            timer=[self.metric_url],
        )

    def test_geoip_miss(self):
        res = self._call(ip='127.0.0.1', status=404)
        self.check_response(res, 'not_found')
        self.check_db_calls(rw=0, ro=0)
        self.check_stats(
            counter=[self.metric_url + '.404'],
            timer=[self.metric_url],
        )

    def test_known_api_key(self):
        res = self._call(api_key='test', ip=self.test_ip)
        self.check_response(res, 'ok')
        self.check_db_calls(rw=0, ro=0)
        self.check_stats(
            counter=[(self.metric_url + '.200', 1),
                     (self.metric + '.api_key.test', 0)],
            timer=[self.metric_url],
        )

    def test_no_api_key(self):
        super(TestView, self).test_no_api_key(status=200, response='ok')
        self.check_db_calls(rw=0, ro=0)
        self.check_stats(
            counter=[(self.metric + '.api_key.no_api_key', 0)],
        )

    def test_unknown_api_key(self):
        super(TestView, self).test_unknown_api_key(
            status=200, response='ok')
        self.check_db_calls(rw=0, ro=0)
        self.check_stats(
            counter=[(self.metric + '.api_key.unknown_key', 0)],
        )

    def test_incomplete_request(self):
        res = self._call(body={'wifiAccessPoints': []}, ip=self.test_ip)
        self.check_response(res, 'ok')
        self.check_db_calls(rw=0, ro=0)
        self.check_stats(
            counter=[self.metric + '.geoip_city_found',
                     self.metric + '.geoip_hit'])

    def test_cell(self):
        # create a cell in the UK
        cell = CellFactory.create(mcc=235)
        query = self.model_query(cells=[cell])
        res = self._call(body=query)
        self.check_model_response(res, cell, country='GB')
        self.check_db_calls(rw=0, ro=0)
        self.check_stats(
            counter=[self.metric + '.cell_hit'])

    def test_wifi(self):
        wifis = WifiFactory.build_batch(2)
        query = self.model_query(wifis=wifis)
        res = self._call(
            body=query,
            ip='127.0.0.1',
            status=404)
        self.check_response(res, 'not_found')
        self.check_db_calls(rw=0, ro=0)
        self.check_stats(
            counter=[self.metric + '.miss'])

    def test_get(self):
        super(TestView, self).test_get()
        self.check_db_calls(rw=0, ro=0)


class TestError(CountryBase, CommonLocateErrorTest):

    def test_database_error(self):
        super(TestError, self).test_database_error(db_errors=0)
