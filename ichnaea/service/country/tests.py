from sqlalchemy import text

from ichnaea.constants import GEOIP_CITY_ACCURACY
from ichnaea.logging import RAVEN_ERROR
from ichnaea.tests.base import (
    AppTestCase,
    FREMONT_IP,
    FREMONT_LAT,
    FREMONT_LON,
)


class CountryBase(object):

    def _make_geoip_query(self, api_key='test', data=None,
                          ip=FREMONT_IP, status=200):
        url = '/v1/country'
        if api_key:
            url = url + '?key=' + api_key
        if data is None:
            data = {}
        extra_environ = None
        if ip:
            extra_environ = {'HTTP_X_FORWARDED_FOR': ip}
        result = self.app.post_json(
            url, data,
            extra_environ=extra_environ,
            status=status)
        self._check_geoip_result(result, status=status)
        return result

    def _check_geoip_result(self, result, status=200):
        self.assertEqual(result.content_type, 'application/json')
        if status == 200:
            self.assertEqual(result.json,
                             {"country_name": "United States",
                              "country_code": "US"})
        elif status == 400:
            self.assertEqual(result.json['error']['message'],
                             'Invalid API key')
        elif status == 404:
            self.assertEqual(result.json['error']['message'],
                             'Not found')


class TestCountry(AppTestCase, CountryBase):

    def test_geoip(self):
        self._make_geoip_query()
        self.check_stats(
            timer=['request.v1.country'],
            counter=['country.api_key.test', 'country.geoip_hit'])

    def test_geoip_miss(self):
        self._make_geoip_query(ip=None, status=404)
        self.check_stats(
            counter=['country.api_key.test', 'country.miss'])

    def test_incomplete_request_means_geoip(self):
        self._make_geoip_query(data={"wifiAccessPoints": []})
        self.check_stats(
            counter=['country.api_key.test', 'country.geoip_hit'])

    def test_no_api_key(self):
        self._make_geoip_query(api_key=None, status=400)
        self.check_stats(
            counter=['country.no_api_key'])

    def test_unknown_api_key(self):
        self._make_geoip_query(api_key='unknown_key', status=400)
        self.check_stats(
            counter=['country.unknown_api_key'])


class TestCountryErrors(AppTestCase, CountryBase):
    # this is a standalone class to ensure DB isolation for dropping tables

    def tearDown(self):
        self.setup_tables(self.db_master.engine)
        super(TestCountryErrors, self).tearDown()

    def test_database_error(self):
        session = self.db_slave_session
        stmt = text("drop table wifi;")
        session.execute(stmt)
        stmt = text("drop table cell;")
        session.execute(stmt)

        self._make_geoip_query()

        self.check_stats(
            timer=['request.v1.country'],
            counter=['request.v1.country.200', 'country.geoip_hit'],
        )
        self.check_expected_heka_messages(
            sentry=[('msg', RAVEN_ERROR, 0)]
        )
