from ichnaea.api.locate.internal import InternalRegionSource
from ichnaea.api.locate.tests.base import BaseSourceTest
from ichnaea.geocode import GEOCODER
from ichnaea.tests.factories import (
    CellFactory,
    WifiShardFactory,
)


class TestRegionSource(BaseSourceTest):

    TestSource = InternalRegionSource
    api_type = 'region'

    def test_from_mcc(self):
        region = GEOCODER.regions_for_mcc(235, metadata=True)[0]
        cell = CellFactory.build(mcc=235)
        query = self.model_query(cells=[cell])
        results = self.source.search(query)
        self.check_model_result(results, region)
        self.check_stats(counter=[
            (self.api_type + '.source',
                ['key:test', 'region:none', 'source:internal',
                 'accuracy:low', 'status:hit']),
        ])

    def test_ambiguous_mcc(self):
        regions = GEOCODER.regions_for_mcc(234, metadata=True)
        cell = CellFactory.build(mcc=234)
        query = self.model_query(cells=[cell])
        results = self.source.search(query)
        self.check_model_result(results, regions)
        self.check_stats(counter=[
            (self.api_type + '.source',
                ['key:test', 'region:none', 'source:internal',
                 'accuracy:low', 'status:hit']),
        ])

    def test_wifi(self):
        wifis = WifiShardFactory.build_batch(2)
        query = self.model_query(wifis=wifis)
        results = self.source.search(query)
        self.check_model_result(results, None)
