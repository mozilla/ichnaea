from sqlalchemy import text

from ichnaea.api.locate.tests.base import (
    BaseLocateTest,
    CommonLocateTest,
)
from ichnaea.tests.base import AppTestCase


class CountryBase(BaseLocateTest):

    url = '/v1/country'
    # disabled metric tracking
    metric = None  # 'country'
    metric_url = None  # 'request.v1.country'

    @property
    def ip_response(self):
        return {'country_code': 'GB', 'country_name': 'United Kingdom'}

    def _make_geoip_query(self, api_key='test', body=None,
                          ip=True, status=200, **kw):
        data = body
        if data is None:
            data = {}
        if ip is True:
            ip = self.test_ip
        return self._call(body=data, api_key=api_key,
                          ip=ip, status=status, **kw)


class TestCountry(AppTestCase, CountryBase, CommonLocateTest):

    track_connection_events = True

    def test_geoip(self):
        res = self._make_geoip_query(status=200)
        self.check_response(res, 'ok')
        self.check_db_calls(rw=0, ro=0)
        self.check_stats(
            counter=['request.v1.country.200'],
            timer=['request.v1.country'],
        )

    def test_geoip_miss(self):
        res = self._make_geoip_query(ip='127.0.0.1', status=404)
        self.check_response(res, 'not_found')
        self.check_db_calls(rw=0, ro=0)
        self.check_stats(
            counter=['request.v1.country.404'],
            timer=['request.v1.country'],
        )

    def test_known_api_key(self):
        res = self._make_geoip_query(api_key='test', status=200)
        self.check_response(res, 'ok')
        self.check_db_calls(rw=0, ro=0)
        self.check_stats(
            counter=[('request.v1.country.200', 1),
                     ('country.api_key.test', 0)],
            timer=['request.v1.country'],
        )

    def test_no_api_key(self):
        super(TestCountry, self).test_no_api_key(status=200, response='ok')
        self.check_db_calls(rw=0, ro=0)
        self.check_stats(
            counter=[('request.v1.country.200', 1),
                     ('country.api_key.no_api_key', 0)],
            timer=['request.v1.country'],
        )

    def test_unknown_api_key(self):
        super(TestCountry, self).test_unknown_api_key(
            status=200, response='ok')
        self.check_db_calls(rw=0, ro=0)
        self.check_stats(
            counter=[('request.v1.country.200', 1),
                     ('country.api_key.unknown_key', 0)],
            timer=['request.v1.country'],
        )

    def test_incomplete_request_means_geoip(self):
        res = self._make_geoip_query(body={'wifiAccessPoints': []})
        self.check_response(res, 'ok')
        self.check_db_calls(rw=0, ro=0)
        self.check_stats(
            counter=['country.geoip_city_found',
                     'country.geoip_hit'])

    def test_no_wifi(self):
        res = self._make_geoip_query(
            ip='127.0.0.1',
            body={'wifiAccessPoints': [{'macAddress': 'ab:cd:ef:12:34:56'}]},
            status=404)
        self.check_response(res, 'not_found')
        self.check_db_calls(rw=0, ro=0)
        self.check_stats(
            counter=['country.miss'])

    def test_get(self):
        super(TestCountry, self).test_get()
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

        res = self._make_geoip_query(status=200)
        self.check_response(res, 'ok')
        self.check_stats(
            counter=['request.v1.country.200'],
            timer=['request.v1.country'],
        )
