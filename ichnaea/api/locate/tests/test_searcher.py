from ichnaea.api.locate.query import Query
from ichnaea.api.locate.searcher import (
    PositionSearcher,
    RegionSearcher,
)
from ichnaea.api.locate.source import (
    PositionSource,
    RegionSource,
)
from ichnaea.tests.base import ConnectionTestCase
from ichnaea.tests.factories import ApiKeyFactory


class DummyRegionSource(RegionSource):

    def search(self, query):
        return self.result_type(
            region_name='Germany', region_code='DE',
            accuracy=100000.0, score=0.5)


class EmptySource(RegionSource):

    def search(self, query):
        return self.result_list()


class DummyPositionSource(PositionSource):
    fallback_field = 'ipf'

    def search(self, query):
        return self.result_type(lat=1.0, lon=1.0, accuracy=1000.0, score=0.5)


class SearcherTest(ConnectionTestCase):

    searcher = None

    def _make_query(self, **kw):
        return Query(api_key=ApiKeyFactory.build(valid_key='test'),
                     api_type='locate',
                     session=self.session,
                     stats_client=self.stats_client,
                     **kw)

    def _init_searcher(self, klass):
        return klass(
            geoip_db=self.geoip_db,
            raven_client=self.raven_client,
            redis_client=self.redis_client,
            stats_client=self.stats_client,
            data_queues=self.data_queues,
        )

    def _search(self, klass, **kw):
        query = self._make_query(**kw)
        searcher = self._init_searcher(klass)
        return searcher.search(query)


class TestSearcher(SearcherTest):

    def test_no_sources(self):
        class TestSearcher(RegionSearcher):
            source_classes = ()

        result = self._search(TestSearcher)
        assert result is None

    def test_no_result(self):
        class TestSearcher(RegionSearcher):
            source_classes = (
                ('test', EmptySource),
            )

        result = self._search(TestSearcher)
        assert result is None

    def test_should_search(self):
        class Source(RegionSource):

            def should_search(self, query, results):
                return False

            def search(self, query):  # pragma: no cover
                raise Exception('The searcher should not reach this point.')

        class TestSearcher(RegionSearcher):
            source_classes = (
                ('test1', DummyRegionSource),
                ('test2', Source),
            )

        result = self._search(TestSearcher)
        assert result['region_code'] == 'DE'


class TestPositionSearcher(SearcherTest):

    def test_result(self):
        class TestSearcher(PositionSearcher):
            source_classes = (
                ('test', DummyPositionSource),
            )

        result = self._search(TestSearcher)
        assert result['lat'] == 1.0
        assert result['lon'] == 1.0
        assert result['accuracy'] == 1000.0
        assert result['fallback'] == 'ipf'


class TestRegionSearcher(SearcherTest):

    def test_result(self):
        class TestSearcher(RegionSearcher):
            source_classes = (
                ('test', DummyRegionSource),
            )

        result = self._search(TestSearcher)
        assert result['region_code'] == 'DE'
        assert result['region_name'] == 'Germany'
