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
from ichnaea.tests.base import ConnectionTestCase
from ichnaea.tests.factories import ApiKeyFactory


class SourceTest(object):

    @classmethod
    def setUpClass(cls):
        super(SourceTest, cls).setUpClass()
        cls.api_key = ApiKeyFactory.build(valid_key='key')
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
        results = self.source.result_list()
        self.assertTrue(self.source.should_search(query, results))


class TestPositionSource(SourceTest, ConnectionTestCase):

    class TestSource(PositionSource):
        fallback_field = 'fallback'
        source = DataSource.fallback

        def search(self, query):
            return self.result_list()

    def test_empty(self):
        query = self._make_query()
        results = self.source.search(query)
        self.assertEqual(len(results), 0)
        self.assertEqual(type(results), PositionResultList)


class TestRegionSource(SourceTest, ConnectionTestCase):

    class TestSource(RegionSource):
        fallback_field = 'ipf'
        source = DataSource.geoip

        def search(self, query):
            return self.result_list()

    def test_empty(self):
        query = self._make_query()
        results = self.source.search(query)
        self.assertEqual(len(results), 0)
        self.assertEqual(type(results), RegionResultList)
