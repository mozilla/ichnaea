from ichnaea.api.locate.geoip import (
    GeoIPPositionSource,
    GeoIPRegionSource,
)
from ichnaea.api.locate.tests.base import BaseSourceTest


class SourceTest(object):

    def test_no_fallback(self, london_model, geoip_db, http_session,
                         session, source, stats):
        query = self.make_query(
            geoip_db, http_session, session, stats,
            ip=london_model.ip,
            fallback={'ipf': False},
        )
        self.check_should_search(source, query, False)

    def test_unknown(self, geoip_db, http_session,
                     session, source, stats):
        query = self.make_query(
            geoip_db, http_session, session, stats,
            ip='127.0.0.1')
        results = source.search(query)
        assert len(results) == 0

    def test_city(self, london_model, geoip_db, http_session,
                  session, source, stats):
        query = self.make_query(
            geoip_db, http_session, session, stats,
            ip=london_model.ip)
        results = source.search(query)
        self.check_model_results(results, [london_model])
        assert 0.5 < results.best().score < 1.0

    def test_region(self, bhutan_model, geoip_db, http_session,
                    session, source, stats):
        query = self.make_query(
            geoip_db, http_session, session, stats,
            ip=bhutan_model.ip)
        results = source.search(query)
        self.check_model_results(results, [bhutan_model])
        assert 0.5 < results.best().score < 1.0


class TestPosition(SourceTest, BaseSourceTest):

    Source = GeoIPPositionSource


class TestRegion(SourceTest, BaseSourceTest):

    Source = GeoIPRegionSource
