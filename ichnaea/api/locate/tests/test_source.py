from ichnaea.api.locate.constants import DataSource
from ichnaea.api.locate.query import Query
from ichnaea.api.locate.result import (
    Country,
    Position,
    ResultList,
)
from ichnaea.api.locate.source import (
    CountrySource,
    PositionSource,
)
from ichnaea.tests.base import ConnectionTestCase
from ichnaea.tests.factories import (
    ApiKeyFactory,
)


class SourceTest(object):

    @classmethod
    def setUpClass(cls):
        super(SourceTest, cls).setUpClass()
        cls.api_key = ApiKeyFactory.build(shortname='key', log=True)
        cls.source = cls.TestSource(
            settings={'foo': '1'},
            geoip_db=cls.geoip_db,
            raven_client=cls.raven_client,
            redis_client=cls.redis_client,
            stats_client=cls.stats_client,
        )

    def _make_query(self, **kw):
        return Query(
            api_key=self.api_key,
            geoip_db=self.geoip_db,
            stats_client=self.stats_client,
            **kw)

    def test_init(self):
        self.assertEqual(self.source.settings, {'foo': '1'})
        self.assertEqual(self.source.geoip_db, self.geoip_db)
        self.assertEqual(self.source.raven_client, self.raven_client)
        self.assertEqual(self.source.redis_client, self.redis_client)
        self.assertEqual(self.source.stats_client, self.stats_client)

    def test_should_search(self):
        query = self._make_query()
        empty = self.source.result_type()
        self.assertTrue(self.source.should_search(query, ResultList(empty)))


class TestCountrySource(SourceTest, ConnectionTestCase):

    class TestSource(CountrySource):
        fallback_field = 'ipf'
        source = DataSource.geoip

        def search(self, query):
            return self.result_type()

    def test_empty(self):
        query = self._make_query()
        result = self.source.search(query)
        self.assertFalse(result.found())
        self.assertTrue(isinstance(result, Country))
        self.assertEqual(result.fallback, 'ipf')
        self.assertEqual(result.source, DataSource.geoip)


class TestPositionSource(SourceTest, ConnectionTestCase):

    class TestSource(PositionSource):
        fallback_field = 'fallback'
        source = DataSource.fallback

        def search(self, query):
            return self.result_type()

    def test_empty(self):
        query = self._make_query()
        result = self.source.search(query)
        self.assertTrue(isinstance(result, Position))
        self.assertFalse(result.found())
        self.assertEqual(result.fallback, 'fallback')
        self.assertEqual(result.source, DataSource.fallback)
