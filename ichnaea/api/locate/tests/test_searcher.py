from ichnaea.api.locate.provider import Provider
from ichnaea.api.locate.query import Query
from ichnaea.api.locate.result import Result
from ichnaea.api.locate.searcher import (
    CountrySearcher,
    PositionSearcher,
    Searcher,
)
from ichnaea.config import DummyConfig
from ichnaea.tests.base import ConnectionTestCase
from ichnaea.tests.factories import ApiKeyFactory


class SearcherTest(ConnectionTestCase):

    searcher = None

    def setUp(self):
        super(SearcherTest, self).setUp()
        self.api_key = ApiKeyFactory.build(shortname='test')
        self.api_name = 'm'
        self.api_type = 'l'

    def _make_query(self, TestResult=None,  # NOQA
                    TestProvider=None, TestSearcher=None):

        if not TestResult:
            class TestResult(Result):

                def accurate_enough(self):
                    return False

                def found(self):
                    return False

                def more_accurate(self, other):
                    return False

        if not TestProvider:
            class TestProvider(Provider):
                result_type = TestResult
                log_name = 'test'

                def search(self, query):
                    return self.result_type()

        if not TestSearcher:
            class TestSearcher(Searcher):
                provider_classes = (
                    ('test', (TestProvider,)),
                )

                def _prepare(self, result):
                    return result

        query = Query(api_key=self.api_key,
                      api_name=self.api_name,
                      api_type=self.api_type,
                      session=self.session,
                      stats_client=self.stats_client)

        return TestSearcher(
            settings=DummyConfig({}),
            geoip_db=self.geoip_db,
            raven_client=self.raven_client,
            redis_client=self.redis_client,
            stats_client=self.stats_client,
        ).search(query)


class TestSearcher(SearcherTest):

    def test_returns_none_with_no_providers(self):

        class TestSearcher(Searcher):
            provider_classes = ()

        result = self._make_query(TestSearcher=TestSearcher)
        self.assertTrue(result is None)
        self.check_stats(
            counter=[
                'm.miss',
                ('m.hit', 0),
            ],
        )

    def test_returns_none_when_provider_returns_no_result(self):
        result = self._make_query()
        self.assertTrue(result is None)
        self.check_stats(
            counter=[
                'm.miss',
                'm.api_log.test.test_miss',
                ('m.api_log.test.test_hit', 0),
            ],
        )

    def test_returns_result_when_provider_result_found(self):

        class TestResult(Result):

            def accurate_enough(self):
                return False

            def found(self):
                return True

            def more_accurate(self, other):
                return True

        result = self._make_query(TestResult=TestResult)
        self.assertTrue(isinstance(result, TestResult))
        self.check_stats(
            counter=[
                'm.test_hit',
                ('m.test_miss', 0),
                'm.api_log.test.test_hit',
                ('m.api_log.test.test_miss', 0),
            ],
        )

    def test_only_searches_providers_when_should_search_is_true(self):

        class TestResult(Result):

            def accurate_enough(self):
                return False

            def found(self):
                return True

            def more_accurate(self, other):
                return True

        class TestProvider1(Provider):
            result_type = TestResult
            log_name = 'test1'

            def should_search(self, query, result):
                return True

            def search(self, query):
                return self.result_type()

        class TestProvider2(Provider):
            result_type = TestResult
            log_name = 'test2'

            def should_search(self, query, result):
                return False

            def search(self, query):
                raise Exception('The searcher should not reach this point.')

        class TestSearcher(Searcher):
            provider_classes = (
                ('test', (
                    TestProvider1,
                    TestProvider2,
                )),
            )

            def _prepare(self, result):
                return result

        result = self._make_query(TestSearcher=TestSearcher)
        self.assertTrue(isinstance(result, TestResult))
        self.check_stats(
            counter=[
                'm.test1_hit',
                'm.api_log.test.test1_hit',
                ('m.test2_hit', 0),
                ('m.api_log.test.test2_hit', 0),
                ('m.api_log.test.test2_miss', 0),
            ],
        )

    def test_accurate_enough_result_halts_search(self):

        class TestResult(Result):

            def accurate_enough(self):
                return True

            def found(self):
                return True

            def more_accurate(self, other):
                return True

        class TestProvider1(Provider):
            result_type = TestResult
            log_name = 'test1'

            def search(self, query):
                return self.result_type()

        class TestProvider2(Provider):
            result_type = TestResult
            log_name = 'test2'

            def search(self, query):
                raise Exception('The searcher should not reach this point.')

        class TestSearcher(Searcher):
            provider_classes = (
                ('test', (
                    TestProvider1,
                    TestProvider2,
                )),
            )

            def _prepare(self, result):
                return result

        result = self._make_query(TestSearcher=TestSearcher)
        self.assertTrue(isinstance(result, TestResult))
        self.check_stats(
            counter=[
                'm.test1_hit',
                'm.api_log.test.test1_hit',
                ('m.test2_hit', 0),
                ('m.api_log.test.test2_hit', 0),
                ('m.api_log.test.test2_miss', 0),
            ],
        )

    def test_last_group_gets_logged_if_had_data(self):

        class TestResult1(Result):

            def accurate_enough(self):
                return False

            def found(self):
                return True

            def more_accurate(self, other):
                return True

        class TestProvider1(Provider):
            result_type = TestResult1
            log_name = 'test1'

            def search(self, query):
                return self.result_type(query_data=True)

        class TestResult2(Result):

            def accurate_enough(self):
                return False

            def found(self):
                return False

            def more_accurate(self, other):
                return False

        class TestProvider2(Provider):
            result_type = TestResult2
            log_name = 'test2'

            def search(self, query):
                return self.result_type(query_data=True)

        class TestSearcher(Searcher):
            provider_classes = (
                ('group1', (TestProvider1, )),
                ('group2', (TestProvider2, )),
            )

            def _prepare(self, result):
                return result

        result = self._make_query(TestSearcher=TestSearcher)
        self.assertTrue(isinstance(result, TestResult1))
        self.check_stats(
            counter=[
                'm.test1_hit',
                'm.api_log.test.test2_miss',
                ('m.test1_miss', 0),
                ('m.api_log.test.test2_hit', 0),
            ],
        )


class TestPositionSearcher(SearcherTest):

    def test_returns_lat_lon_accuracy(self):

        class TestResult(Result):

            def accurate_enough(self):
                return False

            def found(self):
                return True

            def more_accurate(self, other):
                return True

        class TestProvider(Provider):
            result_type = TestResult
            log_name = 'test'
            fallback_field = 'ipf'

            def search(self, query):
                return self.result_type(lat=1.0, lon=1.0, accuracy=1000)

        class TestSearcher(PositionSearcher):
            provider_classes = (
                ('test', (TestProvider,)),
            )

        result = self._make_query(TestSearcher=TestSearcher)
        self.assertAlmostEqual(result['lat'], 1.0)
        self.assertAlmostEqual(result['lon'], 1.0)
        self.assertEqual(result['accuracy'], 1000)
        self.assertEqual(result['fallback'], 'ipf')


class TestCountrySearcher(SearcherTest):

    def test_returns_country_name_and_code(self):

        class TestResult(Result):

            def accurate_enough(self):
                return False

            def found(self):
                return True

            def more_accurate(self, other):
                return True

        class TestProvider(Provider):
            result_type = TestResult
            log_name = 'test'

            def search(self, query):
                return self.result_type(
                    country_name='country', country_code='CO')

        class TestSearcher(CountrySearcher):
            provider_classes = (
                ('test', (TestProvider,)),
            )

        result = self._make_query(TestSearcher=TestSearcher)
        self.assertEqual(result['country_name'], 'country')
        self.assertEqual(result['country_code'], 'CO')
