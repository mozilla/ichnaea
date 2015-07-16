from ichnaea.models import ApiKey
from ichnaea.api.locate.location import Location
from ichnaea.api.locate.provider import Provider
from ichnaea.api.locate.query import Query
from ichnaea.api.locate.searcher import (
    CountrySearcher,
    PositionSearcher,
    Searcher,
)
from ichnaea.tests.base import ConnectionTestCase


class SearcherTest(ConnectionTestCase):

    searcher = None

    def _make_query(self, query=None, TestLocation=None,  # NOQA
                    TestProvider=None, TestSearcher=None):

        if not TestLocation:
            class TestLocation(Location):

                def accurate_enough(self):
                    return False

                def found(self):
                    return False

                def more_accurate(self, other):
                    return False

        if not TestProvider:
            class TestProvider(Provider):
                location_type = TestLocation
                log_name = 'test'

                def locate(self, query):
                    return self.location_type()

        if not TestSearcher:
            class TestSearcher(Searcher):
                provider_classes = (
                    ('test', (TestProvider,)),
                )

                def _prepare(self, location):
                    return location

        query = query or Query()

        return TestSearcher(
            session_db=self.session,
            geoip_db=self.geoip_db,
            redis_client=None,
            settings={},
            api_key=ApiKey(shortname='test', log=True),
            api_name='m',
        ).search(query)


class TestSearcher(SearcherTest):

    def test_returns_none_with_no_providers(self):

        class TestSearcher(Searcher):
            provider_classes = ()

        location = self._make_query(TestSearcher=TestSearcher)
        self.assertTrue(location is None)
        self.check_stats(
            counter=[
                'm.miss',
                ('m.hit', 0),
            ],
        )

    def test_returns_none_when_provider_returns_no_location(self):
        location = self._make_query()
        self.assertTrue(location is None)
        self.check_stats(
            counter=[
                'm.miss',
                'm.api_log.test.test_miss',
                ('m.api_log.test.test_hit', 0),
            ],
        )

    def test_returns_location_when_provider_location_found(self):

        class TestLocation(Location):

            def accurate_enough(self):
                return False

            def found(self):
                return True

            def more_accurate(self, other):
                return True

        location = self._make_query(TestLocation=TestLocation)
        self.assertTrue(isinstance(location, TestLocation))
        self.check_stats(
            counter=[
                'm.test_hit',
                ('m.test_miss', 0),
                'm.api_log.test.test_hit',
                ('m.api_log.test.test_miss', 0),
            ],
        )

    def test_only_searches_providers_when_should_locate_is_true(self):

        class TestLocation(Location):

            def accurate_enough(self):
                return False

            def found(self):
                return True

            def more_accurate(self, other):
                return True

        class TestProvider1(Provider):
            location_type = TestLocation
            log_name = 'test1'

            def should_locate(self, query, location):
                return True

            def locate(self, query):
                return self.location_type()

        class TestProvider2(Provider):
            location_type = TestLocation
            log_name = 'test2'

            def should_locate(self, query, location):
                return False

            def locate(self, query):
                raise Exception('The searcher should not reach this point.')

        class TestSearcher(Searcher):
            provider_classes = (
                ('test', (
                    TestProvider1,
                    TestProvider2,
                )),
            )

            def _prepare(self, location):
                return location

        location = self._make_query(TestSearcher=TestSearcher)
        self.assertTrue(isinstance(location, TestLocation))
        self.check_stats(
            counter=[
                'm.test1_hit',
                'm.api_log.test.test1_hit',
                ('m.test2_hit', 0),
                ('m.api_log.test.test2_hit', 0),
                ('m.api_log.test.test2_miss', 0),
            ],
        )

    def test_accurate_enough_location_halts_search(self):

        class TestLocation(Location):

            def accurate_enough(self):
                return True

            def found(self):
                return True

            def more_accurate(self, other):
                return True

        class TestProvider1(Provider):
            location_type = TestLocation
            log_name = 'test1'

            def locate(self, query):
                return self.location_type()

        class TestProvider2(Provider):
            location_type = TestLocation
            log_name = 'test2'

            def locate(self, query):
                raise Exception('The searcher should not reach this point.')

        class TestSearcher(Searcher):
            provider_classes = (
                ('test', (
                    TestProvider1,
                    TestProvider2,
                )),
            )

            def _prepare(self, location):
                return location

        location = self._make_query(TestSearcher=TestSearcher)
        self.assertTrue(isinstance(location, TestLocation))
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

        class TestLocation1(Location):

            def accurate_enough(self):
                return False

            def found(self):
                return True

            def more_accurate(self, other):
                return True

        class TestProvider1(Provider):
            location_type = TestLocation1
            log_name = 'test1'

            def locate(self, query):
                return self.location_type(query_data=True)

        class TestLocation2(Location):

            def accurate_enough(self):
                return False

            def found(self):
                return False

            def more_accurate(self, other):
                return False

        class TestProvider2(Provider):
            location_type = TestLocation2
            log_name = 'test2'

            def locate(self, query):
                return self.location_type(query_data=True)

        class TestSearcher(Searcher):
            provider_classes = (
                ('group1', (TestProvider1, )),
                ('group2', (TestProvider2, )),
            )

            def _prepare(self, location):
                return location

        location = self._make_query(TestSearcher=TestSearcher)
        self.assertTrue(isinstance(location, TestLocation1))
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

        class TestLocation(Location):

            def accurate_enough(self):
                return False

            def found(self):
                return True

            def more_accurate(self, other):
                return True

        class TestProvider(Provider):
            location_type = TestLocation
            log_name = 'test'
            fallback_field = 'ipf'

            def locate(self, query):
                return self.location_type(lat=1.0, lon=1.0, accuracy=1000)

        class TestSearcher(PositionSearcher):
            provider_classes = (
                ('test', (TestProvider,)),
            )

        location = self._make_query(TestSearcher=TestSearcher)
        self.assertEqual(location['lat'], 1.0)
        self.assertEqual(location['lon'], 1.0)
        self.assertEqual(location['accuracy'], 1000)
        self.assertEqual(location['fallback'], 'ipf')


class TestCountrySearcher(SearcherTest):

    def test_returns_country_name_and_code(self):

        class TestLocation(Location):

            def accurate_enough(self):
                return False

            def found(self):
                return True

            def more_accurate(self, other):
                return True

        class TestProvider(Provider):
            location_type = TestLocation
            log_name = 'test'

            def locate(self, query):
                return self.location_type(
                    country_name='country', country_code='CO')

        class TestSearcher(CountrySearcher):
            provider_classes = (
                ('test', (TestProvider,)),
            )

        location = self._make_query(TestSearcher=TestSearcher)
        self.assertEqual(location['country_name'], 'country')
        self.assertEqual(location['country_code'], 'CO')
