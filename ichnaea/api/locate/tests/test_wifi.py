from datetime import timedelta

import numpy

from ichnaea.api.locate.constants import MAX_WIFIS_IN_CLUSTER
from ichnaea.api.locate.tests.base import BaseSourceTest
from ichnaea.api.locate.wifi import WifiPositionSource
from ichnaea.constants import (
    PERMANENT_BLOCKLIST_THRESHOLD,
)
from ichnaea.tests.factories import WifiShardFactory
from ichnaea import util


class TestWifi(BaseSourceTest):

    TestSource = WifiPositionSource

    def test_wifi(self):
        wifi = WifiShardFactory(radius=50, samples=50)
        wifi2 = WifiShardFactory(
            lat=wifi.lat, lon=wifi.lon + 0.00001, radius=30,
            block_count=1, block_last=None, samples=100)
        self.session.flush()

        query = self.model_query(wifis=[wifi, wifi2])
        results = self.source.search(query)
        self.check_model_results(results, [wifi], lon=wifi.lon + 0.000005)
        self.assertTrue(results.best(query.expected_accuracy).score > 1.0)

    def test_wifi_no_position(self):
        wifi = WifiShardFactory()
        wifi2 = WifiShardFactory(lat=wifi.lat, lon=wifi.lon)
        wifi3 = WifiShardFactory(lat=None, lon=wifi.lon, radius=None)
        self.session.flush()

        query = self.model_query(wifis=[wifi, wifi2, wifi3])
        results = self.source.search(query)
        self.check_model_results(results, [wifi])

    def test_wifi_temp_blocked(self):
        today = util.utcnow().date()
        yesterday = today - timedelta(days=1)
        wifi = WifiShardFactory(radius=200)
        wifi2 = WifiShardFactory(
            lat=wifi.lat, lon=wifi.lon + 0.00001, radius=300,
            block_count=1, block_last=yesterday)
        self.session.flush()

        query = self.model_query(wifis=[wifi, wifi2])
        results = self.source.search(query)
        self.check_model_results(results, None)

    def test_wifi_permanent_blocked(self):
        wifi = WifiShardFactory(radius=200)
        wifi2 = WifiShardFactory(
            lat=wifi.lat, lon=wifi.lon + 0.00001, radius=300,
            block_count=PERMANENT_BLOCKLIST_THRESHOLD, block_last=None)
        self.session.flush()

        query = self.model_query(wifis=[wifi, wifi2])
        results = self.source.search(query)
        self.check_model_results(results, None)

    def test_check_empty(self):
        query = self.model_query()
        results = self.source.result_type().new_list()
        self.assertFalse(self.source.should_search(query, results))

    def test_empty(self):
        query = self.model_query()
        with self.db_call_checker() as check_db_calls:
            results = self.source.search(query)
            self.check_model_results(results, None)
            check_db_calls(rw=0, ro=0)

    def test_few_candidates(self):
        wifis = WifiShardFactory.create_batch(2)
        self.session.flush()

        query = self.model_query(wifis=[wifis[0]])
        results = self.source.search(query)
        self.check_model_results(results, None)

    def test_few_matches(self):
        wifis = WifiShardFactory.create_batch(3)
        wifis[0].lat = None
        self.session.flush()

        query = self.model_query(wifis=wifis[:2])
        results = self.source.search(query)
        self.check_model_results(results, None)

    def test_ignore_outlier(self):
        wifi = WifiShardFactory()
        wifis = WifiShardFactory.create_batch(3, lat=wifi.lat, lon=wifi.lon)
        wifis[0].lat = wifi.lat + 0.0001
        wifis[1].lat = wifi.lat + 0.0002
        wifis[2].lat = wifi.lat + 1.0
        self.session.flush()

        query = self.model_query(wifis=[wifi] + wifis)
        results = self.source.search(query)
        self.check_model_results(results, [wifi], lat=wifi.lat + 0.0001)

    def test_not_closeby(self):
        wifi = WifiShardFactory()
        wifis = [
            WifiShardFactory(lat=wifi.lat + 0.00001, lon=wifi.lon),
            WifiShardFactory(lat=wifi.lat + 1.0, lon=wifi.lon),
            WifiShardFactory(lat=wifi.lat + 1.00001, lon=wifi.lon),
        ]
        self.session.flush()

        query = self.model_query(wifis=[wifi, wifis[1]])
        results = self.source.search(query)
        self.check_model_results(results, None)

    def test_multiple_clusters(self):
        wifi11 = WifiShardFactory()
        wifi12 = WifiShardFactory(lat=wifi11.lat, lon=wifi11.lon)
        wifi21 = WifiShardFactory(lat=wifi11.lat + 1.0, lon=wifi11.lon + 1.0)
        wifi22 = WifiShardFactory(lat=wifi21.lat, lon=wifi21.lon)
        self.session.flush()

        query = self.model_query(wifis=[wifi11, wifi12, wifi21, wifi22])
        query.wifi[0].signal = -100
        query.wifi[1].signal = -80
        query.wifi[2].signal = -100
        query.wifi[3].signal = -54
        results = self.source.search(query)
        self.check_model_results(results, [wifi11, wifi21])

    def test_cluster_score_over_size(self):
        now = util.utcnow()
        yesterday = now - timedelta(days=1)
        last_week = now - timedelta(days=7)
        three_months = now - timedelta(days=90)
        four_months = now - timedelta(days=120)

        wifi11 = WifiShardFactory(
            samples=20, created=last_week, modified=yesterday)
        wifi12 = WifiShardFactory(
            lat=wifi11.lat + 0.0003, lon=wifi11.lon,
            samples=30, created=yesterday, modified=now)
        wifi13 = WifiShardFactory(
            lat=wifi11.lat - 0.0003, lon=wifi11.lon,
            samples=10, created=yesterday, modified=now)
        wifi21 = WifiShardFactory(
            lat=wifi11.lat + 1.0, lon=wifi11.lon + 1.0,
            samples=40, created=four_months, modified=three_months)
        wifi22 = WifiShardFactory(
            lat=wifi21.lat, lon=wifi21.lon,
            samples=50, created=three_months, modified=last_week)
        self.session.flush()

        query = self.model_query(
            wifis=[wifi11, wifi12, wifi13, wifi21, wifi22])
        results = self.source.search(query)
        self.check_model_results(results, [wifi11, wifi21])
        best_result = results.best(query.expected_accuracy)
        self.assertAlmostEqual(best_result.lat, wifi21.lat, 7)
        self.assertAlmostEqual(best_result.lon, wifi21.lon, 7)
        self.assertAlmostEqual(
            best_result.score, wifi21.score(now) + wifi22.score(now), 4)

    def test_top_results_in_noisy_cluster(self):
        now = util.utcnow()
        # all these should wind up in the same cluster since
        # the WiFis are spaced in increments of (+1m, +1.2m)
        wifi1 = WifiShardFactory.build()
        wifis = []
        for i in range(0, MAX_WIFIS_IN_CLUSTER + 10):
            wifis.append(WifiShardFactory(lat=wifi1.lat + i * 0.00001,
                                          lon=wifi1.lon + i * 0.000012,
                                          samples=100 - i))
        self.session.flush()

        # calculate expected result
        lat, lon = numpy.array(
            [(wifi.lat, wifi.lon) for wifi in
             wifis[:MAX_WIFIS_IN_CLUSTER]]).mean(axis=0)
        score = sum([wifi.score(now) for wifi in wifis])

        query = self.model_query(wifis=wifis)
        for i, entry in enumerate(query.wifi):
            entry.signal = -70 - i
        results = self.source.search(query)
        self.check_model_results(results, [wifi1], lat=lat, lon=lon)
        self.assertAlmostEqual(
            results.best(query.expected_accuracy).score, score, 4)
