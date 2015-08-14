from ichnaea.api.locate.constants import DataSource
from ichnaea.api.locate.query import Query
from ichnaea.api.locate.searcher import (
    CountrySearcher,
    PositionSearcher,
)
from ichnaea.api.locate.source import (
    CountrySource,
    PositionSource,
)
from ichnaea.config import DummyConfig
from ichnaea.tests.base import ConnectionTestCase
from ichnaea.tests.factories import ApiKeyFactory


class TestCountrySource(CountrySource):

    def search(self, query):
        return self.result_type(
            country_name='Germany', country_code='DE', accuracy=100000.0)


class TestEmptySource(CountrySource):

    def search(self, query):
        return self.result_type()


class TestPositionSource(PositionSource):
    fallback_field = 'ipf'

    def search(self, query):
        return self.result_type(lat=1.0, lon=1.0, accuracy=1000.0)


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
        class TestSearcher(CountrySearcher):
            source_classes = ()

        result = self._search(TestSearcher)
        self.assertTrue(result is None)

    def test_no_result(self):
        class TestSearcher(CountrySearcher):
            source_classes = (
                ('test', TestEmptySource),
            )

        result = self._search(TestSearcher)
        self.assertTrue(result is None)

    def test_should_search(self):
        class TestSource(CountrySource):

            def should_search(self, query, results):
                return False

            def search(self, query):
                raise Exception('The searcher should not reach this point.')

        class TestSearcher(CountrySearcher):
            source_classes = (
                ('test1', TestCountrySource),
                ('test2', TestSource),
            )

        result = self._search(TestSearcher)
        self.assertEqual(result['country_code'], 'DE')

    def test_satisfies(self):
        class TestSource1(TestCountrySource):
            source = DataSource.internal

        class TestSource2(TestCountrySource):
            source = DataSource.geoip

            def should_search(self, query, results):
                return True

            def search(self, query):
                raise Exception('The searcher should not reach this point.')

        class TestSearcher(CountrySearcher):
            source_classes = (
                ('test1', TestSource1),
                ('test1', TestSource2),
            )

        result = self._search(TestSearcher)
        self.assertEqual(result['country_code'], 'DE')


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


class TestCountrySearcher(SearcherTest):

    def test_result(self):
        class TestSearcher(CountrySearcher):
            source_classes = (
                ('test', TestCountrySource),
            )

        result = self._search(TestSearcher)
        self.assertEqual(result['country_code'], 'DE')
        self.assertEqual(result['country_name'], 'Germany')
