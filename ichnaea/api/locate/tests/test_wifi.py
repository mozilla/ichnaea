from datetime import timedelta

from ichnaea.api.locate.constants import DataSource, MAX_WIFIS_IN_CLUSTER
from ichnaea.api.locate.score import station_score
from ichnaea.api.locate.source import PositionSource
from ichnaea.api.locate.tests.base import BaseSourceTest
from ichnaea.api.locate.wifi import WifiPositionMixin
from ichnaea.tests.factories import WifiShardFactory
from ichnaea import util


class WifiTestPositionSource(WifiPositionMixin, PositionSource):

    fallback_field = None
    source = DataSource.internal

    def should_search(self, query, results):
        return self.should_search_wifi(query, results)

    def search(self, query):
        return self.search_wifi(query)


class TestWifi(BaseSourceTest):

    Source = WifiTestPositionSource

    def test_wifi(self, geoip_db, http_session, session, source, stats):
        wifi = WifiShardFactory(radius=5, samples=50)
        wifi2 = WifiShardFactory(
            lat=wifi.lat, lon=wifi.lon + 0.00001, radius=5, samples=100
        )
        session.flush()

        query = self.model_query(
            geoip_db, http_session, session, stats, wifis=[wifi, wifi2]
        )
        query.wifi[0].signalStrength = -60
        query.wifi[1].signalStrength = -80
        results = source.search(query)
        self.check_model_results(results, [wifi], lon=wifi.lon + 0.000004)
        assert results.best().score > 1.0

    def test_wifi_no_position(self, geoip_db, http_session, session, source, stats):
        wifi = WifiShardFactory()
        wifi2 = WifiShardFactory(lat=wifi.lat, lon=wifi.lon)
        wifi3 = WifiShardFactory(lat=None, lon=wifi.lon, radius=None)
        session.flush()

        query = self.model_query(
            geoip_db, http_session, session, stats, wifis=[wifi, wifi2, wifi3]
        )
        results = source.search(query)
        self.check_model_results(results, [wifi])

    def test_wifi_temp_blocked(self, geoip_db, http_session, session, source, stats):
        today = util.utcnow()
        yesterday = today - timedelta(days=1)
        wifi = WifiShardFactory(radius=200)
        wifi2 = WifiShardFactory(
            lat=wifi.lat,
            lon=wifi.lon + 0.00001,
            radius=300,
            created=yesterday,
            modified=today,
            block_first=yesterday.date(),
            block_last=yesterday.date(),
            block_count=1,
        )
        session.flush()

        query = self.model_query(
            geoip_db, http_session, session, stats, wifis=[wifi, wifi2]
        )
        results = source.search(query)
        self.check_model_results(results, None)

    def test_wifi_permanent_blocked(
        self, geoip_db, http_session, session, source, stats
    ):
        now = util.utcnow()
        last_week = now - timedelta(days=7)
        three_months = now - timedelta(days=90)
        four_months = now - timedelta(days=120)

        wifi = WifiShardFactory(radius=200)
        wifi2 = WifiShardFactory(
            lat=wifi.lat,
            lon=wifi.lon + 0.00001,
            radius=300,
            created=four_months,
            modified=now,
            block_first=three_months.date(),
            block_last=last_week.date(),
            block_count=4,
        )
        session.flush()

        query = self.model_query(
            geoip_db, http_session, session, stats, wifis=[wifi, wifi2]
        )
        results = source.search(query)
        self.check_model_results(results, None)

    def test_check_empty(self, geoip_db, http_session, session, source, stats):
        query = self.model_query(geoip_db, http_session, session, stats)
        results = source.result_list()
        assert not source.should_search(query, results)

    def test_empty(
        self,
        geoip_db,
        http_session,
        raven,
        redis,
        session_tracker,
        session,
        source,
        stats,
    ):
        query = self.model_query(geoip_db, http_session, session, stats)
        results = source.search(query)
        self.check_model_results(results, None)
        session_tracker(0)

    def test_few_candidates(self, geoip_db, http_session, session, source, stats):
        wifis = WifiShardFactory.create_batch(2)
        session.flush()

        query = self.model_query(
            geoip_db, http_session, session, stats, wifis=[wifis[0]]
        )
        results = source.search(query)
        self.check_model_results(results, None)

    def test_few_matches(self, geoip_db, http_session, session, source, stats):
        wifis = WifiShardFactory.create_batch(3)
        wifis[0].lat = None
        session.flush()

        query = self.model_query(
            geoip_db, http_session, session, stats, wifis=wifis[:2]
        )
        results = source.search(query)
        self.check_model_results(results, None)

    def test_ignore_outlier(self, geoip_db, http_session, session, source, stats):
        wifi = WifiShardFactory()
        wifis = WifiShardFactory.create_batch(3, lat=wifi.lat, lon=wifi.lon, radius=5)
        wifis[0].lat = wifi.lat + 0.00001
        wifis[1].lat = wifi.lat + 0.00002
        wifis[2].lat = wifi.lat + 1.0
        session.flush()

        query = self.model_query(
            geoip_db, http_session, session, stats, wifis=[wifi] + wifis
        )
        results = source.search(query)
        self.check_model_results(results, [wifi], lat=wifi.lat + 0.00001)
        assert round(results.best().score, 4) == 0.15

    def test_not_closeby(self, geoip_db, http_session, session, source, stats):
        wifi = WifiShardFactory()
        wifis = [
            WifiShardFactory(lat=wifi.lat + 0.00001, lon=wifi.lon),
            WifiShardFactory(lat=wifi.lat + 1.0, lon=wifi.lon),
            WifiShardFactory(lat=wifi.lat + 1.00001, lon=wifi.lon),
        ]
        session.flush()

        query = self.model_query(
            geoip_db, http_session, session, stats, wifis=[wifi, wifis[1]]
        )
        results = source.search(query)
        self.check_model_results(results, None)

    def test_multiple_clusters(self, geoip_db, http_session, session, source, stats):
        wifi11 = WifiShardFactory()
        wifi12 = WifiShardFactory(lat=wifi11.lat, lon=wifi11.lon)
        wifi21 = WifiShardFactory(lat=wifi11.lat + 1.0, lon=wifi11.lon + 1.0)
        wifi22 = WifiShardFactory(lat=wifi21.lat, lon=wifi21.lon)
        session.flush()

        query = self.model_query(
            geoip_db,
            http_session,
            session,
            stats,
            wifis=[wifi11, wifi12, wifi21, wifi22],
        )
        query.wifi[0].signalStrength = -100
        query.wifi[1].signalStrength = -80
        query.wifi[2].signalStrength = -100
        query.wifi[3].signalStrength = -54
        results = source.search(query)
        self.check_model_results(results, [wifi11, wifi21])

    def test_cluster_score_over_size(
        self, geoip_db, http_session, session, source, stats
    ):
        now = util.utcnow()
        yesterday = now - timedelta(days=1)
        last_week = now - timedelta(days=7)
        three_months = now - timedelta(days=90)
        four_months = now - timedelta(days=120)

        wifi11 = WifiShardFactory(samples=20, created=last_week, modified=yesterday)
        wifi12 = WifiShardFactory(
            lat=wifi11.lat + 0.00003,
            lon=wifi11.lon,
            samples=30,
            created=yesterday,
            modified=now,
        )
        wifi13 = WifiShardFactory(
            lat=wifi11.lat - 0.00003,
            lon=wifi11.lon,
            samples=10,
            created=yesterday,
            modified=now,
        )
        wifi21 = WifiShardFactory(
            lat=wifi11.lat + 1.0,
            lon=wifi11.lon + 1.0,
            samples=40,
            created=four_months,
            modified=three_months,
        )
        wifi22 = WifiShardFactory(
            lat=wifi21.lat,
            lon=wifi21.lon,
            samples=50,
            created=three_months,
            modified=last_week,
        )
        session.flush()

        query = self.model_query(
            geoip_db,
            http_session,
            session,
            stats,
            wifis=[wifi11, wifi12, wifi13, wifi21, wifi22],
        )
        results = source.search(query)
        assert len(results) == 2
        best_result = results.best()
        assert round(best_result.lat, 7) == round(wifi21.lat, 7)
        assert round(best_result.lon, 7) == round(wifi21.lon, 7)
        assert round(best_result.accuracy, 2) == 10.0
        assert round(best_result.score, 2) == round(
            station_score(wifi21, now) + station_score(wifi22, now), 2
        )
        other_result = [res for res in results if res.score < best_result.score][0]
        assert round(other_result.lat, 4) == round(wifi11.lat, 4)
        assert round(other_result.lon, 4) == round(wifi11.lon, 4)

    def test_top_results_in_noisy_cluster(
        self, geoip_db, http_session, session, source, stats
    ):
        now = util.utcnow()
        # all these should wind up in the same cluster since
        # the WiFis are spaced in increments of (+0.1m, +0.12m)
        wifi1 = WifiShardFactory.build()
        wifis = []
        for i in range(0, MAX_WIFIS_IN_CLUSTER + 10):
            wifis.append(
                WifiShardFactory(
                    lat=wifi1.lat + i * 0.000001,
                    lon=wifi1.lon + i * 0.0000012,
                    samples=100 - i,
                )
            )
        session.flush()

        # calculate expected result
        score = sum([station_score(wifi, now) for wifi in wifis])

        query = self.model_query(geoip_db, http_session, session, stats, wifis=wifis)
        for i, entry in enumerate(query.wifi):
            entry.signalStrength = -50 - i

        results = source.search(query)
        result = results.best()
        assert round(result.lat, 4) == round(wifi1.lat, 4)
        assert round(result.lon, 4) == round(wifi1.lon, 4)
        assert round(result.score, 4) == round(score, 4)

    def test_weight(self, geoip_db, http_session, session, source, stats):
        wifi1 = WifiShardFactory.build()
        wifis = []
        for i in range(4):
            wifis.append(
                WifiShardFactory(
                    lat=wifi1.lat + i * 0.0001, lon=wifi1.lon + i * 0.00012
                )
            )
        session.flush()

        query = self.model_query(geoip_db, http_session, session, stats, wifis=wifis)
        query.wifi[0].signalStrength = -10
        query.wifi[0].age = 0
        query.wifi[1].signalStrength = -40
        query.wifi[1].age = 8000
        query.wifi[2].signalStrength = -70
        query.wifi[2].age = 16000
        query.wifi[3].signalStrength = -100

        results = source.search(query)
        result = results.best()
        assert round(result.lat, 7) == wifi1.lat + 0.0000009
        assert round(result.lon, 7) == wifi1.lon + 0.0000006
        assert round(result.accuracy, 2) == 39.51
