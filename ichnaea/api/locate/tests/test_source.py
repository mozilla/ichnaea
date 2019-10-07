from ichnaea.api.locate.constants import DataSource
from ichnaea.api.locate.query import Query
from ichnaea.api.locate.result import PositionResultList, RegionResultList
from ichnaea.api.locate.source import PositionSource, RegionSource
from ichnaea.tests.factories import KeyFactory


class SourceTest(object):
    def _make_query(self, geoip_db, **kw):
        return Query(api_key=KeyFactory(valid_key="test"), geoip_db=geoip_db, **kw)

    def test_init(self, geoip_db, raven, redis, source):
        assert source.geoip_db == geoip_db
        assert source.raven_client == raven
        assert source.redis_client == redis

    def test_should_search(self, geoip_db, source):
        query = self._make_query(geoip_db)
        results = source.result_list()
        assert source.should_search(query, results)


class TestPositionSource(SourceTest):
    class Source(PositionSource):
        fallback_field = "fallback"
        source = DataSource.fallback

        def search(self, query):
            return self.result_list()

    def test_empty(self, geoip_db, source):
        query = self._make_query(geoip_db)
        results = source.search(query)
        assert len(results) == 0
        assert type(results) is PositionResultList


class TestRegionSource(SourceTest):
    class Source(RegionSource):
        fallback_field = "ipf"
        source = DataSource.geoip

        def search(self, query):
            return self.result_list()

    def test_empty(self, geoip_db, source):
        query = self._make_query(geoip_db)
        results = source.search(query)
        assert len(results) == 0
        assert type(results) is RegionResultList
