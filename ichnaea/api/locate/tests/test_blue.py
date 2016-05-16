from ichnaea.api.locate.blue import BluePositionMixin
from ichnaea.api.locate.constants import (
    DataSource,
)
from ichnaea.api.locate.source import PositionSource
from ichnaea.api.locate.tests.base import BaseSourceTest
from ichnaea.tests.factories import BlueShardFactory


class BlueTestPositionSource(BluePositionMixin, PositionSource):
    """
    Implements a search using our Bluetooth data.

    This source is only used in tests.
    """

    fallback_field = None  #:
    source = DataSource.internal

    def should_search(self, query, results):
        return self.should_search_blue(query, results)

    def search(self, query):
        return self.search_blue(query)


class TestBlue(BaseSourceTest):

    Source = BlueTestPositionSource

    def test_should_search(self, geoip_db, http_session,
                           session, source, stats):
        query = self.make_query(geoip_db, http_session, session, stats)
        self.check_should_search(source, query, False)

    def test_blue(self, geoip_db, http_session, session, source, stats):
        blue = BlueShardFactory(radius=10, samples=50)
        blue2 = BlueShardFactory(
            lat=blue.lat, lon=blue.lon + 0.00001, radius=100,
            block_last=None, samples=100)
        session.flush()

        query = self.model_query(
            geoip_db, http_session, session, stats,
            blues=[blue, blue2])
        query.blue[0].signalStrength = -80
        query.blue[1].signalStrength = -90
        results = source.search(query)
        self.check_model_results(results, [blue], lon=blue.lon + 0.0000048)
        assert results.best().score > 1.0
