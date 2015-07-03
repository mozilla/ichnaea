from sqlalchemy import text

from ichnaea.api.exceptions import (
    InvalidAPIKey,
    LocationNotFound,
)
from ichnaea.tests.base import AppTestCase


class CountryBase(object):

    @property
    def test_ip(self):
        # accesses data defined in GeoIPTestCase
        return self.geoip_data['London']['ip']

    def _make_geoip_query(self, api_key='test', data=None,
                          ip=None, status=200):
        url = '/v1/country'
        if api_key:
            url = url + '?key=' + api_key
        if data is None:
            data = {}
        extra_environ = None
        if ip is None:
            ip = self.test_ip
        if ip:
            extra_environ = {'HTTP_X_FORWARDED_FOR': ip}
        result = self.app.post_json(
            url, data,
            extra_environ=extra_environ,
            status=status)
        return result

    def _check_geoip_result(self, result, status=200):
        self.assertEqual(result.content_type, 'application/json')
        self.assertEqual(result.charset, 'UTF-8')
        if status == 200:
            self.assertEqual(result.json,
                             {'country_name': 'United Kingdom',
                              'country_code': 'GB'})
        elif status == 400:
            self.assertEqual(result.json, InvalidAPIKey.json_body())
        elif status == 404:
            self.assertEqual(result.json, LocationNotFound.json_body())


class TestCountry(AppTestCase, CountryBase):

    track_connection_events = True

    def test_geoip(self):
        result = self._make_geoip_query(status=200)
        self._check_geoip_result(result, status=200)
        self.check_db_calls(rw=0, ro=0)
        self.check_stats(
            counter=['request.v1.country.200'],
            timer=['request.v1.country'],
        )

    def test_geoip_miss(self):
        result = self._make_geoip_query(ip='127.0.0.1', status=404)
        self._check_geoip_result(result, status=404)
        self.check_db_calls(rw=0, ro=0)
        self.check_stats(
            counter=['request.v1.country.404'],
            timer=['request.v1.country'],
        )

    def test_known_api_key(self):
        result = self._make_geoip_query(api_key='test', status=200)
        self._check_geoip_result(result, status=200)
        self.check_db_calls(rw=0, ro=0)
        self.check_stats(
            counter=[('request.v1.country.200', 1),
                     ('country.api_key.test', 0)],
            timer=['request.v1.country'],
        )

    def test_no_api_key(self):
        result = self._make_geoip_query(api_key=None, status=200)
        self._check_geoip_result(result, status=200)
        self.check_db_calls(rw=0, ro=0)
        self.check_stats(
            counter=[('request.v1.country.200', 1),
                     ('country.api_key.no_api_key', 0)],
            timer=['request.v1.country'],
        )

    def test_unknown_api_key(self):
        result = self._make_geoip_query(api_key='unknown_key', status=200)
        self._check_geoip_result(result, status=200)
        self.check_db_calls(rw=0, ro=0)
        self.check_stats(
            counter=[('request.v1.country.200', 1),
                     ('country.api_key.unknown_key', 0)],
            timer=['request.v1.country'],
        )

    def test_incomplete_request_means_geoip(self):
        result = self._make_geoip_query(data={'wifiAccessPoints': []})
        self._check_geoip_result(result, status=200)
        self.check_db_calls(rw=0, ro=0)
        self.check_stats(
            counter=['country.geoip_city_found',
                     'country.geoip_hit'])

    def test_no_wifi(self):
        result = self._make_geoip_query(
            ip='127.0.0.1',
            data={'wifiAccessPoints': [{'macAddress': 'ab:cd:ef:12:34:56'}]},
            status=404)
        self._check_geoip_result(result, status=404)
        self.check_db_calls(rw=0, ro=0)
        self.check_stats(
            counter=['country.miss'])

    def test_get_fallback(self):
        result = self.app.get(
            '/v1/country?key=test',
            extra_environ={'HTTP_X_FORWARDED_FOR': self.test_ip},
            status=200)
        self._check_geoip_result(result)
        self.check_db_calls(rw=0, ro=0)


class TestCountryErrors(AppTestCase, CountryBase):
    # this is a standalone class to ensure DB isolation for dropping tables

    def tearDown(self):
        self.setup_tables(self.db_rw.engine)
        super(TestCountryErrors, self).tearDown()

    def test_database_error(self):
        for tablename in ('wifi', 'cell', 'cell_area',
                          'ocid_cell', 'ocid_cell_area'):
            stmt = text('drop table %s;' % tablename)
            self.session.execute(stmt)

        result = self._make_geoip_query(status=200)
        self._check_geoip_result(result, status=200)
        self.check_stats(
            counter=['request.v1.country.200'],
            timer=['request.v1.country'],
        )
