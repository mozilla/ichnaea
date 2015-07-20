from ichnaea.api.locate.geoip import (
    GeoIPCountryProvider,
    GeoIPPositionProvider,
)
from ichnaea.api.locate.tests.test_provider import GeoIPProviderTest


class TestGeoIPPositionProvider(GeoIPProviderTest):

    TestProvider = GeoIPPositionProvider

    def test_geoip_provider_should_not_search_if_ipf_disabled(self):
        query = self.model_query(
            geoip='127.0.0.1',
            fallbacks={'ipf': False},
        )
        self.check_should_search(query, False)

    def test_geoip_unknown(self):
        query = self.model_query(geoip='127.0.0.1')
        result = self.provider.search(query)
        self.check_model_result(result, None, used=True)

    def test_geoip_city(self):
        query = self.model_query(geoip=self.london_model.ip)
        result = self.provider.search(query)
        self.check_model_result(result, self.london_model)

    def test_geoip_country(self):
        query = self.model_query(geoip=self.bhutan_model.ip)
        result = self.provider.search(query)
        self.check_model_result(result, self.bhutan_model)


class TestGeoIPCountryProvider(GeoIPProviderTest):

    TestProvider = GeoIPCountryProvider

    def test_geoip_unknown(self):
        query = self.model_query(geoip='127.0.0.1')
        result = self.provider.search(query)
        self.check_model_result(result, None, used=True)

    def test_geoip_country(self):
        query = self.model_query(geoip=self.bhutan_model.ip)
        result = self.provider.search(query)
        self.check_model_result(result, self.bhutan_model)
