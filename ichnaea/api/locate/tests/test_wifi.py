from ichnaea.api.locate.tests.test_provider import ProviderTest
from ichnaea.api.locate.wifi import WifiPositionProvider
from ichnaea.constants import WIFI_MIN_ACCURACY
from ichnaea.tests.factories import WifiFactory


class TestWifiPositionProvider(ProviderTest):

    TestProvider = WifiPositionProvider

    def test_wifi(self):
        wifi = WifiFactory(range=200)
        wifi2 = WifiFactory(lat=wifi.lat, lon=wifi.lon + 0.00001, range=300)
        self.session.flush()

        query = self.model_query(wifis=[wifi, wifi2])
        location = self.provider.locate(query)
        self.check_model_location(
            location, wifi,
            lon=wifi.lon + 0.000005, accuracy=WIFI_MIN_ACCURACY)

    def test_wifi_too_few_candidates(self):
        wifis = WifiFactory.create_batch(2)
        self.session.flush()

        query = self.model_query(wifis=[wifis[0]])
        location = self.provider.locate(query)
        self.check_model_location(location, None)

    def test_wifi_too_few_matches(self):
        wifis = WifiFactory.create_batch(3)
        wifis[0].lat = None
        self.session.flush()

        query = self.model_query(wifis=wifis[:2])
        location = self.provider.locate(query)
        self.check_model_location(location, None, used=True)

    def test_wifi_too_similar_bssids_by_arithmetic_difference(self):
        wifi = WifiFactory(key='00000000001f')
        wifi2 = WifiFactory(key='000000000020')
        self.session.flush()

        query = self.model_query(wifis=[wifi, wifi2])
        location = self.provider.locate(query)
        self.check_model_location(location, None)

    def test_wifi_too_similar_bssids_by_hamming_distance(self):
        wifi = WifiFactory(key='000000000058')
        wifi2 = WifiFactory(key='00000000005c')
        self.session.flush()

        query = self.model_query(wifis=[wifi, wifi2])
        location = self.provider.locate(query)
        self.check_model_location(location, None)

    def test_wifi_similar_bssids_but_enough_clusters(self):
        wifi11 = WifiFactory(key='00000000001f')
        wifi12 = WifiFactory(key='000000000020',
                             lat=wifi11.lat, lon=wifi11.lon)
        wifi21 = WifiFactory(key='000000000058',
                             lat=wifi11.lat + 0.00004,
                             lon=wifi11.lon + 0.00004)
        wifi22 = WifiFactory(key='00000000005c',
                             lat=wifi21.lat, lon=wifi21.lon)
        self.session.flush()

        query = self.model_query(wifis=[wifi11, wifi12, wifi21, wifi22])
        location = self.provider.locate(query)
        self.check_model_location(
            location, wifi11,
            lat=wifi11.lat + 0.00002, lon=wifi11.lon + 0.00002)

    def test_wifi_similar_bssids_but_enough_found_clusters(self):
        wifi = WifiFactory(key='00000000001f')
        wifi2 = WifiFactory(key='000000000024',
                            lat=wifi.lat + 0.00004, lon=wifi.lon + 0.00004)
        other_wifi = [
            WifiFactory.build(key='000000000020'),
            WifiFactory.build(key='000000000021'),
            WifiFactory.build(key='000000000022'),
            WifiFactory.build(key='000000000023'),
        ]
        self.session.flush()

        query = self.model_query(wifis=[wifi, wifi2] + other_wifi)
        location = self.provider.locate(query)
        self.check_model_location(
            location, wifi,
            lat=wifi.lat + 0.00002, lon=wifi.lon + 0.00002)

    def test_wifi_ignore_outlier(self):
        wifi = WifiFactory()
        wifis = WifiFactory.create_batch(3, lat=wifi.lat, lon=wifi.lon)
        wifis[0].lat = wifi.lat + 0.0001
        wifis[1].lat = wifi.lat + 0.0002
        wifis[2].lat = wifi.lat + 1.0
        self.session.flush()

        query = self.model_query(wifis=[wifi] + wifis)
        location = self.provider.locate(query)
        self.check_model_location(
            location, wifi, lat=wifi.lat + 0.0001)

    def test_wifi_prefer_cluster_with_better_signals(self):
        wifi11 = WifiFactory()
        wifi12 = WifiFactory(lat=wifi11.lat + 0.0002, lon=wifi11.lon)
        wifi21 = WifiFactory(lat=wifi11.lat + 1.0, lon=wifi11.lon + 1.0)
        wifi22 = WifiFactory(lat=wifi21.lat + 0.0002, lon=wifi21.lon)
        self.session.flush()

        query = self.model_query(wifis=[wifi11, wifi12, wifi21, wifi22])
        query.wifi[0].signal = -100
        query.wifi[1].signal = -80
        query.wifi[2].signal = -100
        query.wifi[3].signal = -54
        location = self.provider.locate(query)
        self.check_model_location(
            location, wifi21, lat=wifi21.lat + 0.0001)

    def test_wifi_prefer_larger_cluster_over_high_signal(self):
        wifi = WifiFactory()
        wifis = WifiFactory.create_batch(3, lat=wifi.lat, lon=wifi.lon)
        wifis2 = WifiFactory.create_batch(3, lat=wifi.lat + 1.0, lon=wifi.lon)
        self.session.flush()

        query = self.model_query(wifis=[wifi] + wifis + wifis2)
        for entry in query.wifi[:-3]:
            entry.signal = -80
        for entry in query.wifi[-3:]:
            entry.signal = -70
        location = self.provider.locate(query)
        self.check_model_location(location, wifi)

    def test_wifi_only_use_top_five_signals_in_noisy_cluster(self):
        # all these should wind up in the same cluster since
        # clustering threshold is 500m and the 10 wifis are
        # spaced in increments of (+1m, +1.2m)
        wifi = WifiFactory.build()
        wifis = []
        for i in range(0, 10):
            wifis.append(WifiFactory(lat=wifi.lat + i * 0.00001,
                                     lon=wifi.lon + i * 0.000012))

        self.session.flush()

        query = self.model_query(wifis=wifis)
        for i, entry in enumerate(query.wifi):
            entry.signal = -70 - i
        location = self.provider.locate(query)
        self.check_model_location(
            location, wifi,
            lat=wifi.lat + 0.00002,
            lon=wifi.lon + 0.000024)

    def test_wifi_not_closeby(self):
        wifi = WifiFactory()
        wifis = [
            WifiFactory(lat=wifi.lat + 0.00001, lon=wifi.lon),
            WifiFactory(lat=wifi.lat + 1.0, lon=wifi.lon),
            WifiFactory(lat=wifi.lat + 1.00001, lon=wifi.lon),
        ]
        self.session.flush()

        query = self.model_query(wifis=[wifi, wifis[1]])
        location = self.provider.locate(query)
        self.check_model_location(location, None, used=True)
