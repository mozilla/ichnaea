from ichnaea.api.locate.query import Query
from ichnaea.api.locate.searcher import PositionSearcher, RegionSearcher
from ichnaea.api.locate.source import PositionSource, RegionSource
from ichnaea.tests.factories import KeyFactory


class DummyRegionSource(RegionSource):
    def search(self, query):
        return self.result_type(
            region_name="Germany", region_code="DE", accuracy=100000.0, score=0.5
        )


class EmptySource(RegionSource):
    def search(self, query):
        return self.result_list()


class DummyPositionSource(PositionSource):
    fallback_field = "ipf"

    def search(self, query):
        return self.result_type(lat=1.0, lon=1.0, accuracy=1000.0, score=0.5)


class SearcherTest(object):

    searcher = None

    def _search(self, data_queues, geoip_db, raven, redis, session, klass, **kw):
        query = Query(
            api_key=KeyFactory(valid_key="test"),
            api_type="locate",
            session=session,
            **kw,
        )
        searcher = klass(
            geoip_db=geoip_db,
            raven_client=raven,
            redis_client=redis,
            data_queues=data_queues,
        )
        return searcher.search(query)


class TestSearcher(SearcherTest):
    def test_no_sources(self, data_queues, geoip_db, raven, redis, session):
        class TestSearcher(RegionSearcher):
            source_classes = ()

        result = self._search(
            data_queues, geoip_db, raven, redis, session, TestSearcher
        )
        assert result is None

    def test_no_result(self, data_queues, geoip_db, raven, redis, session):
        class TestSearcher(RegionSearcher):
            source_classes = (("test", EmptySource),)

        result = self._search(
            data_queues, geoip_db, raven, redis, session, TestSearcher
        )
        assert result is None

    def test_should_search(self, data_queues, geoip_db, raven, redis, session):
        class Source(RegionSource):
            def should_search(self, query, results):
                return False

            def search(self, query):
                raise Exception("The searcher should not reach this point.")

        class TestSearcher(RegionSearcher):
            source_classes = (("test1", DummyRegionSource), ("test2", Source))

        result = self._search(
            data_queues, geoip_db, raven, redis, session, TestSearcher
        )
        assert result["region_code"] == "DE"


class TestPositionSearcher(SearcherTest):
    def test_result(self, data_queues, geoip_db, raven, redis, session):
        class TestSearcher(PositionSearcher):
            source_classes = (("test", DummyPositionSource),)

        result = self._search(
            data_queues, geoip_db, raven, redis, session, TestSearcher
        )
        assert result["lat"] == 1.0
        assert result["lon"] == 1.0
        assert result["accuracy"] == 1000.0
        assert result["fallback"] == "ipf"


class TestRegionSearcher(SearcherTest):
    def test_result(self, data_queues, geoip_db, raven, redis, session):
        class TestSearcher(RegionSearcher):
            source_classes = (("test", DummyRegionSource),)

        result = self._search(
            data_queues, geoip_db, raven, redis, session, TestSearcher
        )
        assert result["region_code"] == "DE"
        assert result["region_name"] == "Germany"
