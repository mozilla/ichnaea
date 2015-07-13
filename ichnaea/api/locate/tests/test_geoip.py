from ichnaea.api.locate.geoip import (
    GeoIPCountryProvider,
    GeoIPPositionProvider,
)
from ichnaea.api.locate.tests.test_provider import GeoIPProviderTest


class TestGeoIPPositionProvider(GeoIPProviderTest):

    TestProvider = GeoIPPositionProvider

    def test_geoip_provider_should_not_locate_if_ipf_disabled(self):
        query = self.model_query(
            geoip='127.0.0.1',
            fallbacks={'ipf': False},
        )
        self.check_should_locate(query, False)

    def test_geoip_unknown(self):
        query = self.model_query(geoip='127.0.0.1')
        location = self.provider.locate(query)
        self.check_model_location(location, None, used=True)

    def test_geoip_city(self):
        query = self.model_query(geoip=self.london_model.ip)
        location = self.provider.locate(query)
        self.check_model_location(location, self.london_model)

    def test_geoip_country(self):
        query = self.model_query(geoip=self.bhutan_model.ip)
        location = self.provider.locate(query)
        self.check_model_location(location, self.bhutan_model)


class TestGeoIPCountryProvider(GeoIPProviderTest):

    TestProvider = GeoIPCountryProvider

    def test_geoip_unknown(self):
        query = self.model_query(geoip='127.0.0.1')
        location = self.provider.locate(query)
        self.check_model_location(location, None, used=True)

    def test_geoip_country(self):
        query = self.model_query(geoip=self.bhutan_model.ip)
        location = self.provider.locate(query)
        self.check_model_location(location, self.bhutan_model)
