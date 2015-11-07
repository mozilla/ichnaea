from datetime import timedelta

import numpy

from ichnaea.api.locate.constants import MAX_WIFIS_IN_CLUSTER
from ichnaea.api.locate.result import ResultList
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
        wifi = WifiShardFactory(radius=50)
        wifi2 = WifiShardFactory(
            lat=wifi.lat, lon=wifi.lon + 0.00001, radius=30,
            block_count=1, block_last=None)
        self.session.flush()

        query = self.model_query(wifis=[wifi, wifi2])
        result = self.source.search(query)
        self.check_model_result(result, wifi, lon=wifi.lon + 0.000005)

    def test_wifi_no_position(self):
        wifi = WifiShardFactory()
        wifi2 = WifiShardFactory(lat=wifi.lat, lon=wifi.lon)
        wifi3 = WifiShardFactory(lat=None, lon=wifi.lon, radius=None)
        self.session.flush()

        query = self.model_query(wifis=[wifi, wifi2, wifi3])
        result = self.source.search(query)
        self.check_model_result(result, wifi)

    def test_wifi_temp_blocked(self):
        today = util.utcnow().date()
        yesterday = today - timedelta(days=1)
        wifi = WifiShardFactory(radius=200)
        wifi2 = WifiShardFactory(
            lat=wifi.lat, lon=wifi.lon + 0.00001, radius=300,
            block_count=1, block_last=yesterday)
        self.session.flush()

        query = self.model_query(wifis=[wifi, wifi2])
        result = self.source.search(query)
        self.check_model_result(result, None)

    def test_wifi_permanent_blocked(self):
        wifi = WifiShardFactory(radius=200)
        wifi2 = WifiShardFactory(
            lat=wifi.lat, lon=wifi.lon + 0.00001, radius=300,
            block_count=PERMANENT_BLOCKLIST_THRESHOLD, block_last=None)
        self.session.flush()

        query = self.model_query(wifis=[wifi, wifi2])
        result = self.source.search(query)
        self.check_model_result(result, None)

    def test_check_empty(self):
        query = self.model_query()
        result = self.source.result_type()
        self.assertFalse(self.source.should_search(query, ResultList(result)))

    def test_empty(self):
        query = self.model_query()
        with self.db_call_checker() as check_db_calls:
            result = self.source.search(query)
            self.check_model_result(result, None)
            check_db_calls(rw=0, ro=0)

    def test_few_candidates(self):
        wifis = WifiShardFactory.create_batch(2)
        self.session.flush()

        query = self.model_query(wifis=[wifis[0]])
        result = self.source.search(query)
        self.check_model_result(result, None)

    def test_few_matches(self):
        wifis = WifiShardFactory.create_batch(3)
        wifis[0].lat = None
        self.session.flush()

        query = self.model_query(wifis=wifis[:2])
        result = self.source.search(query)
        self.check_model_result(result, None)

    def test_ignore_outlier(self):
        wifi = WifiShardFactory()
        wifis = WifiShardFactory.create_batch(3, lat=wifi.lat, lon=wifi.lon)
        wifis[0].lat = wifi.lat + 0.0001
        wifis[1].lat = wifi.lat + 0.0002
        wifis[2].lat = wifi.lat + 1.0
        self.session.flush()

        query = self.model_query(wifis=[wifi] + wifis)
        result = self.source.search(query)
        self.check_model_result(
            result, wifi, lat=wifi.lat + 0.0001)

    def test_cluster_size_over_better_signal(self):
        wifi11 = WifiShardFactory()
        wifi12 = WifiShardFactory(lat=wifi11.lat + 0.0002, lon=wifi11.lon)
        wifi21 = WifiShardFactory(lat=wifi11.lat + 1.0, lon=wifi11.lon + 1.0)
        wifi22 = WifiShardFactory(lat=wifi21.lat + 0.0002, lon=wifi21.lon)
        self.session.flush()

        query = self.model_query(wifis=[wifi11, wifi12, wifi21, wifi22])
        query.wifi[0].signal = -100
        query.wifi[1].signal = -80
        query.wifi[2].signal = -100
        query.wifi[3].signal = -54
        result = self.source.search(query)
        self.check_model_result(
            result, wifi21, lat=wifi21.lat + 0.0001)

    def test_larger_cluster_over_signal(self):
        wifi = WifiShardFactory()
        wifis = WifiShardFactory.create_batch(
            3, lat=wifi.lat, lon=wifi.lon)
        wifis2 = WifiShardFactory.create_batch(
            3, lat=wifi.lat + 1.0, lon=wifi.lon)
        self.session.flush()

        query = self.model_query(wifis=[wifi] + wifis + wifis2)
        for entry in query.wifi[:-3]:
            entry.signal = -80
        for entry in query.wifi[-3:]:
            entry.signal = -70
        result = self.source.search(query)
        self.check_model_result(result, wifi)

    def test_top_results_in_noisy_cluster(self):
        # all these should wind up in the same cluster since
        # the WiFis are spaced in increments of (+1m, +1.2m)
        wifi1 = WifiShardFactory.build()
        wifis = []
        for i in range(0, MAX_WIFIS_IN_CLUSTER + 10):
            wifis.append(WifiShardFactory(lat=wifi1.lat + i * 0.00001,
                                          lon=wifi1.lon + i * 0.000012))
        self.session.flush()

        # calculate expected result
        lat, lon = numpy.array(
            [(wifi.lat, wifi.lon) for wifi in
             wifis[:MAX_WIFIS_IN_CLUSTER]]).mean(axis=0)

        query = self.model_query(wifis=wifis)
        for i, entry in enumerate(query.wifi):
            entry.signal = -70 - i
        result = self.source.search(query)
        self.check_model_result(result, wifi1, lat=lat, lon=lon)

    def test_wifi_not_closeby(self):
        wifi = WifiShardFactory()
        wifis = [
            WifiShardFactory(lat=wifi.lat + 0.00001, lon=wifi.lon),
            WifiShardFactory(lat=wifi.lat + 1.0, lon=wifi.lon),
            WifiShardFactory(lat=wifi.lat + 1.00001, lon=wifi.lon),
        ]
        self.session.flush()

        query = self.model_query(wifis=[wifi, wifis[1]])
        result = self.source.search(query)
        self.check_model_result(result, None)
