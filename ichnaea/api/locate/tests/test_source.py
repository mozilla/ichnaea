from ichnaea.api.locate.constants import DataSource
from ichnaea.api.locate.query import Query
from ichnaea.api.locate.result import (
    PositionResultList,
    RegionResultList,
)
from ichnaea.api.locate.source import (
    PositionSource,
    RegionSource,
)
from ichnaea.tests.factories import ApiKeyFactory


class SourceTest(object):

    def _make_query(self, geoip_db, stats, **kw):
        return Query(
            api_key=ApiKeyFactory.build(valid_key='test'),
            geoip_db=geoip_db,
            stats_client=stats,
            **kw)

    def test_init(self, geoip_db, raven, redis, source, stats):
        assert source.geoip_db == geoip_db
        assert source.raven_client == raven
        assert source.redis_client == redis
        assert source.stats_client == stats

    def test_should_search(self, geoip_db, source, stats):
        query = self._make_query(geoip_db, stats)
        results = source.result_list()
        assert source.should_search(query, results)


class TestPositionSource(SourceTest):

    class Source(PositionSource):
        fallback_field = 'fallback'
        source = DataSource.fallback

        def search(self, query):
            return self.result_list()

    def test_empty(self, geoip_db, source, stats):
        query = self._make_query(geoip_db, stats)
        results = source.search(query)
        assert len(results) == 0
        assert type(results) is PositionResultList


class TestRegionSource(SourceTest):

    class Source(RegionSource):
        fallback_field = 'ipf'
        source = DataSource.geoip

        def search(self, query):
            return self.result_list()

    def test_empty(self, geoip_db, source, stats):
        query = self._make_query(geoip_db, stats)
        results = source.search(query)
        assert len(results) == 0
        assert type(results) is RegionResultList
