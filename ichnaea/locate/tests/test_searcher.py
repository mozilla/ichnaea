from ichnaea.locate.location import Location
from ichnaea.locate.location_provider import LocationProvider
from ichnaea.locate.location_searcher import (
    CountrySearcher,
    LocationSearcher,
    PositionSearcher,
)
from ichnaea.tests.base import (
    DBTestCase,
    GeoIPIsolation,
)


class LocationSearcherTest(DBTestCase, GeoIPIsolation):

    default_session = 'db_ro_session'
    searcher = None

    @classmethod
    def setUpClass(cls):
        DBTestCase.setUpClass()
        GeoIPIsolation.setup_geoip(raven_client=cls.raven_client)

    @classmethod
    def tearDownClass(cls):
        GeoIPIsolation.teardown_geoip()
        DBTestCase.tearDownClass()

    def _make_query(self, data=None, TestLocation=None,
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
            class TestProvider(LocationProvider):
                location_type = TestLocation
                log_name = 'test'

                def locate(self, data):
                    return self.location_type()

        if not TestSearcher:
            class TestSearcher(LocationSearcher):
                provider_classes = (
                    ('test', (TestProvider,)),
                )

                def prepare_location(self, location):
                    return location

        return TestSearcher(
            {'geoip': self.geoip_db, 'session': self.session},
            api_key_log=True,
            api_key_name='test',
            api_name='m',
        ).search(data)


class TestLocationSearcher(LocationSearcherTest):

    def test_searcher_with_no_providers_returns_None(self):

        class TestSearcher(LocationSearcher):
            provider_classes = ()

        location = self._make_query(TestSearcher=TestSearcher)
        self.assertEqual(location, None)
        self.check_stats(
            counter=[
                'm.miss',
            ],
        )

    def test_searcher_returns_None_when_provider_returns_no_location(self):

        location = self._make_query()
        self.assertEqual(location, None)
        self.check_stats(
            counter=[
                'm.miss',
                'm.api_log.test.test_miss',
            ],
        )

    def test_searcher_returns_location_when_provider_location_found(self):

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
                'm.api_log.test.test_hit',
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

        class TestProvider1(LocationProvider):
            location_type = TestLocation
            log_name = 'test1'

            def locate(self, data):
                return self.location_type()

        class TestProvider2(LocationProvider):
            location_type = TestLocation
            log_name = 'test2'

            def locate(self, data):
                raise Exception('The searcher should not reach this point.')

        class TestSearcher(LocationSearcher):
            provider_classes = (
                ('test', (
                    TestProvider1,
                    TestProvider2,
                )),
            )

            def prepare_location(self, location):
                return location

        location = self._make_query(TestSearcher=TestSearcher)
        self.assertTrue(isinstance(location, TestLocation))
        self.check_stats(
            counter=[
                'm.test1_hit',
                'm.api_log.test.test1_hit',
            ],
        )


class TestPositionSearcher(LocationSearcherTest):

    def test_position_searcher_returns_lat_lon_accuracy(self):

        class TestLocation(Location):

            def accurate_enough(self):
                return False

            def found(self):
                return True

            def more_accurate(self, other):
                return True

        class TestProvider(LocationProvider):
            location_type = TestLocation
            log_name = 'test'

            def locate(self, data):
                return self.location_type(lat=1.0, lon=1.0, accuracy=1000)

        class TestSearcher(PositionSearcher):
            provider_classes = (
                ('test', (TestProvider,)),
            )

        location = self._make_query(TestSearcher=TestSearcher)
        self.assertEqual(location['lat'], 1.0)
        self.assertEqual(location['lon'], 1.0)
        self.assertEqual(location['accuracy'], 1000)


class TestCountrySearcher(LocationSearcherTest):

    def test_country_searcher_returns_country_name_and_code(self):

        class TestLocation(Location):

            def accurate_enough(self):
                return False

            def found(self):
                return True

            def more_accurate(self, other):
                return True

        class TestProvider(LocationProvider):
            location_type = TestLocation
            log_name = 'test'

            def locate(self, data):
                return self.location_type(
                    country_name='country', country_code='CO')

        class TestSearcher(CountrySearcher):
            provider_classes = (
                ('test', (TestProvider,)),
            )

        location = self._make_query(TestSearcher=TestSearcher)
        self.assertEqual(location['country_name'], 'country')
        self.assertEqual(location['country_code'], 'CO')
