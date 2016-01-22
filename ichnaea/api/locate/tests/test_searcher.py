from ichnaea.api.locate.query import Query
from ichnaea.api.locate.searcher import (
    PositionSearcher,
    RegionSearcher,
)
from ichnaea.api.locate.source import (
    PositionSource,
    RegionSource,
)
from ichnaea.config import DummyConfig
from ichnaea.tests.base import ConnectionTestCase
from ichnaea.tests.factories import ApiKeyFactory


class TestRegionSource(RegionSource):

    def search(self, query):
        return self.result_type(
            region_name='Germany', region_code='DE',
            accuracy=100000.0, score=0.5)


class TestEmptySource(RegionSource):

    def search(self, query):
        return self.result_type().new_list()


class TestPositionSource(PositionSource):
    fallback_field = 'ipf'

    def search(self, query):
        return self.result_type(lat=1.0, lon=1.0, accuracy=1000.0, score=0.5)


class SearcherTest(ConnectionTestCase):

    searcher = None

    def setUp(self):
        super(SearcherTest, self).setUp()
        self.api_key = ApiKeyFactory.build(shortname='test')
        self.api_type = 'locate'

    def _make_query(self, **kw):
        return Query(api_key=self.api_key,
                     api_type=self.api_type,
                     session=self.session,
                     stats_client=self.stats_client,
                     **kw)

    def _init_searcher(self, klass):
        return klass(
            settings=DummyConfig({}),
            geoip_db=self.geoip_db,
            raven_client=self.raven_client,
            redis_client=self.redis_client,
            stats_client=self.stats_client,
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
        self.assertTrue(result is None)

    def test_no_result(self):
        class TestSearcher(RegionSearcher):
            source_classes = (
                ('test', TestEmptySource),
            )

        result = self._search(TestSearcher)
        self.assertTrue(result is None)

    def test_should_search(self):
        class TestSource(RegionSource):

            def should_search(self, query, results):
                return False

            def search(self, query):
                raise Exception('The searcher should not reach this point.')

        class TestSearcher(RegionSearcher):
            source_classes = (
                ('test1', TestRegionSource),
                ('test2', TestSource),
            )

        result = self._search(TestSearcher)
        self.assertEqual(result['region_code'], 'DE')


class TestPositionSearcher(SearcherTest):

    def test_result(self):
        class TestSearcher(PositionSearcher):
            source_classes = (
                ('test', TestPositionSource),
            )

        result = self._search(TestSearcher)
        self.assertAlmostEqual(result['lat'], 1.0)
        self.assertAlmostEqual(result['lon'], 1.0)
        self.assertAlmostEqual(result['accuracy'], 1000.0)
        self.assertEqual(result['fallback'], 'ipf')


class TestRegionSearcher(SearcherTest):

    def test_result(self):
        class TestSearcher(RegionSearcher):
            source_classes = (
                ('test', TestRegionSource),
            )

        result = self._search(TestSearcher)
        self.assertEqual(result['region_code'], 'DE')
        self.assertEqual(result['region_name'], 'Germany')
