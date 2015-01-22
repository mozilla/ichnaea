from sqlalchemy import text

from ichnaea.logging import RAVEN_ERROR
from ichnaea.tests.base import AppTestCase


class CountryBase(object):

    @property
    def test_ip(self):
        # accesses data defined in GeoIPIsolation
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
                             {"country_name": "United Kingdom",
                              "country_code": "GB"})
        elif status == 400:
            self.assertEqual(result.json['error']['message'],
                             'Invalid API key')
        elif status == 404:
            self.assertEqual(result.json['error']['message'],
                             'Not found')


class TestCountry(AppTestCase, CountryBase):

    track_connection_events = True

    def test_geoip(self):
        result = self._make_geoip_query(status=200)
        self._check_geoip_result(result, status=200)
        self.check_db_calls(master=0, slave=0)
        self.check_stats(
            total=2,
            counter=['request.v1.country.200'],
            timer=['request.v1.country'],
        )

    def test_geoip_miss(self):
        result = self._make_geoip_query(ip='127.0.0.1', status=404)
        self._check_geoip_result(result, status=404)
        self.check_db_calls(master=0, slave=0)
        self.check_stats(
            total=2,
            counter=['request.v1.country.404'],
            timer=['request.v1.country'],
        )

    def test_no_api_key(self):
        result = self._make_geoip_query(api_key=None, status=200)
        self._check_geoip_result(result, status=200)
        self.check_db_calls(master=0, slave=0)
        self.check_stats(
            total=2,
            counter=['request.v1.country.200'],
            timer=['request.v1.country'],
        )

    def test_unknown_api_key(self):
        result = self._make_geoip_query(api_key='unknown_key', status=200)
        self._check_geoip_result(result, status=200)
        self.check_db_calls(master=0, slave=0)
        self.check_stats(
            total=2,
            counter=['request.v1.country.200'],
            timer=['request.v1.country'],
        )

    def test_incomplete_request_means_geoip(self):
        result = self._make_geoip_query(data={"wifiAccessPoints": []})
        self._check_geoip_result(result, status=200)
        self.check_db_calls(master=0, slave=0)
        self.check_stats(
            counter=['country.geoip_city_found',
                     'country.country_from_geoip',
                     'country.geoip_hit'])

    def test_no_wifi(self):
        result = self._make_geoip_query(
            ip='127.0.0.1',
            data={"wifiAccessPoints": [{"macAddress": "ab:cd:ef:12:34:56"}]},
            status=404)
        self._check_geoip_result(result, status=404)
        self.check_db_calls(master=0, slave=0)
        self.check_stats(
            counter=['country.no_geoip_found',
                     'country.no_country',
                     'country.no_wifi_found',
                     'country.miss'])


class TestCountryErrors(AppTestCase, CountryBase):
    # this is a standalone class to ensure DB isolation for dropping tables

    def tearDown(self):
        self.setup_tables(self.db_master.engine)
        super(TestCountryErrors, self).tearDown()

    def test_database_error(self):
        session = self.db_slave_session
        for tablename in ('wifi', 'cell', 'cell_area',
                          'ocid_cell', 'ocid_cell_area'):
            stmt = text("drop table %s;" % tablename)
            session.execute(stmt)

        result = self._make_geoip_query(status=200)
        self._check_geoip_result(result, status=200)
        self.check_stats(
            total=2,
            counter=['request.v1.country.200'],
            timer=['request.v1.country'],
        )
        self.check_expected_heka_messages(
            sentry=[('msg', RAVEN_ERROR, 0)]
        )
