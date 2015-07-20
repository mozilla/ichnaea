from ichnaea.api.locate.geoip import (
    GeoIPCountrySource,
    GeoIPPositionSource,
)
from ichnaea.api.locate.tests.base import BaseSourceTest


class SourceTest(object):

    def test_no_fallback(self):
        query = self.make_query(
            ip=self.london_model.ip,
            fallback={'ipf': False},
        )
        self.check_should_search(query, False)

    def test_unknown(self):
        query = self.make_query(ip='127.0.0.1')
        result = self.source.search(query)
        self.assertFalse(result.found())

    def test_city(self):
        query = self.make_query(ip=self.london_model.ip)
        result = self.source.search(query)
        self.check_model_result(result, self.london_model)

    def test_country(self):
        query = self.make_query(ip=self.bhutan_model.ip)
        result = self.source.search(query)
        self.check_model_result(result, self.bhutan_model)


class TestPositionSource(SourceTest, BaseSourceTest):

    TestSource = GeoIPPositionSource


class TestCountrySource(SourceTest, BaseSourceTest):

    TestSource = GeoIPCountrySource
