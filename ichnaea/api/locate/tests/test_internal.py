from ichnaea.api.locate.internal import InternalRegionSource
from ichnaea.api.locate.tests.base import BaseSourceTest
from ichnaea.geocode import GEOCODER
from ichnaea.tests.factories import (
    CellShardFactory,
    WifiShardFactory,
)


class TestRegionSource(BaseSourceTest):

    TestSource = InternalRegionSource
    api_type = 'region'

    def test_from_mcc(self):
        region = GEOCODER.regions_for_mcc(235, metadata=True)[0]
        cell = CellShardFactory.build(mcc=235)
        query = self.model_query(cells=[cell])
        results = self.source.search(query)
        self.check_model_result(results, region)
        self.assertAlmostEqual(results[0].score, 2.0, 4)
        self.check_stats(counter=[
            (self.api_type + '.source',
                ['key:test', 'region:none', 'source:internal',
                 'accuracy:low', 'status:hit']),
        ])

    def test_ambiguous_mcc(self):
        regions = GEOCODER.regions_for_mcc(234, metadata=True)
        cell = CellShardFactory.build(mcc=234)
        query = self.model_query(cells=[cell])
        results = self.source.search(query)
        self.check_model_result(results, regions)
        for result in results:
            self.assertAlmostEqual(result.score, 0.5, 4)
        self.check_stats(counter=[
            (self.api_type + '.source',
                ['key:test', 'region:none', 'source:internal',
                 'accuracy:low', 'status:hit']),
        ])

    def test_multiple_mcc(self):
        region = GEOCODER.regions_for_mcc(235, metadata=True)[0]
        cell = CellShardFactory.build(mcc=234)
        cell2 = CellShardFactory.build(mcc=235)
        query = self.model_query(cells=[cell, cell2])
        results = self.source.search(query)
        self.assertTrue(len(results) > 2)
        best_result = results.best(query.expected_accuracy)
        self.assertEqual(best_result.region_code, region.code)
        self.assertAlmostEqual(best_result.score, 2.5, 4)

    def test_invalid_mcc(self):
        cell = CellShardFactory.build(mcc=235)
        cell.mcc = 999
        query = self.model_query(cells=[cell])
        results = self.source.search(query)
        self.check_model_result(results, None)

    def test_wifi(self):
        wifis = WifiShardFactory.build_batch(2)
        query = self.model_query(wifis=wifis)
        results = self.source.search(query)
        self.check_model_result(results, None)
