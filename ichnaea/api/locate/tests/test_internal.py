from ichnaea.api.locate.internal import InternalRegionSource
from ichnaea.api.locate.score import area_score, station_score
from ichnaea.api.locate.tests.base import BaseSourceTest
from ichnaea.geocode import GEOCODER
from ichnaea.tests.factories import BlueShardFactory, CellAreaFactory, WifiShardFactory
from ichnaea import util


class TestRegionSource(BaseSourceTest):

    Source = InternalRegionSource
    api_type = "region"

    def test_blue(self, geoip_db, http_session, session, source, metricsmock):
        now = util.utcnow()
        region = GEOCODER.regions_for_mcc(235, metadata=True)[0]
        blue1 = BlueShardFactory(samples=10)
        blue2 = BlueShardFactory(samples=20)
        blue3 = BlueShardFactory.build(region="DE", samples=100)
        session.flush()

        query = self.model_query(
            geoip_db, http_session, session, blues=[blue1, blue2, blue3]
        )
        results = source.search(query)
        self.check_model_results(results, [region])
        best_result = results.best()
        assert best_result.region_code == region.code
        assert best_result.score == station_score(blue1, now) + station_score(
            blue2, now
        )
        assert metricsmock.has_record(
            "incr",
            self.api_type + ".source",
            value=1,
            tags=[
                "key:test",
                "region:none",
                "source:internal",
                "accuracy:low",
                "status:hit",
            ],
        )

    def test_blue_miss(self, geoip_db, http_session, session, source):
        blues = BlueShardFactory.build_batch(2, samples=10)
        session.flush()

        query = self.model_query(geoip_db, http_session, session, blues=blues)
        results = source.search(query)
        self.check_model_results(results, None)

    def test_from_mcc(self, geoip_db, http_session, session, source, metricsmock):
        region = GEOCODER.regions_for_mcc(235, metadata=True)[0]
        area = CellAreaFactory(mcc=235, num_cells=10)
        session.flush()

        query = self.model_query(geoip_db, http_session, session, cells=[area])
        results = source.search(query)
        self.check_model_results(results, [region])
        assert results[0].score == 1.0
        assert metricsmock.has_record(
            "incr",
            self.api_type + ".source",
            value=1,
            tags=[
                "key:test",
                "region:none",
                "source:internal",
                "accuracy:low",
                "status:hit",
            ],
        )

    def test_ambiguous_mcc(self, geoip_db, http_session, session, source, metricsmock):
        now = util.utcnow()
        regions = GEOCODER.regions_for_mcc(234, metadata=True)
        area = CellAreaFactory(mcc=234, num_cells=10)
        session.flush()

        query = self.model_query(geoip_db, http_session, session, cells=[area])
        results = source.search(query)
        self.check_model_results(results, regions)
        assert results.best().region_code == "GB"
        for result in results:
            score = 0.25
            if result.region_code == "GB":
                score += area_score(area, now)
            assert result.score == score
        assert metricsmock.has_record(
            "incr",
            self.api_type + ".source",
            value=1,
            tags=[
                "key:test",
                "region:none",
                "source:internal",
                "accuracy:low",
                "status:hit",
            ],
        )

    def test_multiple_mcc(self, geoip_db, http_session, session, source):
        now = util.utcnow()
        region = GEOCODER.regions_for_mcc(235, metadata=True)[0]
        area = CellAreaFactory(mcc=234, num_cells=6)
        area2 = CellAreaFactory(mcc=235, num_cells=8)
        session.flush()

        query = self.model_query(geoip_db, http_session, session, cells=[area, area2])
        results = source.search(query)
        assert len(results) > 2
        best_result = results.best()
        assert best_result.region_code == region.code
        assert best_result.score == 1.25 + area_score(area, now)

    def test_invalid_mcc(self, geoip_db, http_session, session, source):
        area = CellAreaFactory.build(mcc=235, num_cells=10)
        area.mcc = 999
        query = self.model_query(geoip_db, http_session, session, cells=[area])
        results = source.search(query)
        self.check_model_results(results, None)

    def test_wifi(self, geoip_db, http_session, session, source, metricsmock):
        now = util.utcnow()
        region = GEOCODER.regions_for_mcc(235, metadata=True)[0]
        wifi1 = WifiShardFactory(samples=10)
        wifi2 = WifiShardFactory(samples=20)
        wifi3 = WifiShardFactory.build(region="DE", samples=100)
        session.flush()

        query = self.model_query(
            geoip_db, http_session, session, wifis=[wifi1, wifi2, wifi3]
        )
        results = source.search(query)
        self.check_model_results(results, [region])
        best_result = results.best()
        assert best_result.region_code == region.code
        assert best_result.score == station_score(wifi1, now) + station_score(
            wifi2, now
        )
        assert metricsmock.has_record(
            "incr",
            self.api_type + ".source",
            value=1,
            tags=[
                "key:test",
                "region:none",
                "source:internal",
                "accuracy:low",
                "status:hit",
            ],
        )

    def test_wifi_miss(self, geoip_db, http_session, session, source):
        wifis = WifiShardFactory.build_batch(2, samples=10)
        session.flush()

        query = self.model_query(geoip_db, http_session, session, wifis=wifis)
        results = source.search(query)
        self.check_model_results(results, None)
