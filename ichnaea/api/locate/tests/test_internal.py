from ichnaea.api.locate.internal import InternalRegionSource
from ichnaea.api.locate.tests.base import BaseSourceTest
from ichnaea.geocode import GEOCODER
from ichnaea.tests.factories import (
    BlueShardFactory,
    CellAreaFactory,
    WifiShardFactory,
)
from ichnaea import util


class TestRegionSource(BaseSourceTest):

    Source = InternalRegionSource
    api_type = 'region'

    def test_blue(self):
        now = util.utcnow()
        region = GEOCODER.regions_for_mcc(235, metadata=True)[0]
        blue1 = BlueShardFactory(samples=10)
        blue2 = BlueShardFactory(samples=20)
        blue3 = BlueShardFactory.build(region='DE', samples=100)
        self.session.flush()

        query = self.model_query(blues=[blue1, blue2, blue3])
        results = self.source.search(query)
        self.check_model_results(results, [region])
        best_result = results.best()
        assert best_result.region_code == region.code
        assert best_result.score == blue1.score(now) + blue2.score(now)
        self.check_stats(counter=[
            (self.api_type + '.source',
                ['key:test', 'region:none', 'source:internal',
                 'accuracy:low', 'status:hit']),
        ])

    def test_blue_miss(self):
        blues = BlueShardFactory.build_batch(2, samples=10)
        self.session.flush()

        query = self.model_query(blues=blues)
        results = self.source.search(query)
        self.check_model_results(results, None)

    def test_from_mcc(self):
        region = GEOCODER.regions_for_mcc(235, metadata=True)[0]
        cell = CellAreaFactory(mcc=235, num_cells=10)
        self.session.flush()

        query = self.model_query(cells=[cell])
        results = self.source.search(query)
        self.check_model_results(results, [region])
        assert results[0].score == 1.0
        self.check_stats(counter=[
            (self.api_type + '.source',
                ['key:test', 'region:none', 'source:internal',
                 'accuracy:low', 'status:hit']),
        ])

    def test_ambiguous_mcc(self):
        now = util.utcnow()
        regions = GEOCODER.regions_for_mcc(234, metadata=True)
        cell = CellAreaFactory(mcc=234, num_cells=10)
        self.session.flush()

        query = self.model_query(cells=[cell])
        results = self.source.search(query)
        self.check_model_results(results, regions)
        assert results.best().region_code == 'GB'
        for result in results:
            score = 0.25
            if result.region_code == 'GB':
                score += cell.score(now)
            assert result.score == score
        self.check_stats(counter=[
            (self.api_type + '.source',
                ['key:test', 'region:none', 'source:internal',
                 'accuracy:low', 'status:hit']),
        ])

    def test_multiple_mcc(self):
        now = util.utcnow()
        region = GEOCODER.regions_for_mcc(235, metadata=True)[0]
        cell = CellAreaFactory(mcc=234, num_cells=6)
        cell2 = CellAreaFactory(mcc=235, num_cells=8)
        self.session.flush()

        query = self.model_query(cells=[cell, cell2])
        results = self.source.search(query)
        assert len(results) > 2
        best_result = results.best()
        assert best_result.region_code == region.code
        assert best_result.score == 1.25 + cell.score(now)

    def test_invalid_mcc(self):
        cell = CellAreaFactory.build(mcc=235, num_cells=10)
        cell.mcc = 999
        query = self.model_query(cells=[cell])
        results = self.source.search(query)
        self.check_model_results(results, None)

    def test_wifi(self):
        now = util.utcnow()
        region = GEOCODER.regions_for_mcc(235, metadata=True)[0]
        wifi1 = WifiShardFactory(samples=10)
        wifi2 = WifiShardFactory(samples=20)
        wifi3 = WifiShardFactory.build(region='DE', samples=100)
        self.session.flush()

        query = self.model_query(wifis=[wifi1, wifi2, wifi3])
        results = self.source.search(query)
        self.check_model_results(results, [region])
        best_result = results.best()
        assert best_result.region_code == region.code
        assert best_result.score == wifi1.score(now) + wifi2.score(now)
        self.check_stats(counter=[
            (self.api_type + '.source',
                ['key:test', 'region:none', 'source:internal',
                 'accuracy:low', 'status:hit']),
        ])

    def test_wifi_miss(self):
        wifis = WifiShardFactory.build_batch(2, samples=10)
        self.session.flush()

        query = self.model_query(wifis=wifis)
        results = self.source.search(query)
        self.check_model_results(results, None)
