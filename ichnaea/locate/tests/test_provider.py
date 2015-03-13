import mobile_codes
import random

from ichnaea.constants import (
    LAC_MIN_ACCURACY,
    WIFI_MIN_ACCURACY,
)
from ichnaea.locate.location_provider import (
    AbstractLocationProvider,
    AbstractCellLocationProvider,
    AbstractCellAreaLocationProvider,
    CellCountryProvider,
    WifiLocationProvider,
)
from ichnaea.models.cell import (
    Cell,
    CellArea,
    Radio,
)
from ichnaea.models.wifi import (
    Wifi,
)
from ichnaea.tests.base import (
    DBTestCase,
    GB_LAT,
    GB_LON,
    GB_MCC,
)
from ichnaea.locate.location import CountryLocation, PositionLocation


class AbstractLocationProviderTest(DBTestCase):

    default_session = 'db_ro_session'

    class TestProvider(AbstractLocationProvider):
        location_type = PositionLocation
        log_name = 'test'

    def setUp(self):
        super(AbstractLocationProviderTest, self).setUp()

        self.provider = self.TestProvider(
            self.session,
            api_key_log=True,
            api_key_name='test',
            api_name='m',
        )


class TestAbstractLocationProvider(AbstractLocationProviderTest):

    def test_log_hit(self):
        self.provider.log_hit()
        self.check_stats(
            counter=[
                'm.test_hit',
            ],
        )

    def test_log_success(self):
        self.provider.log_success()
        self.check_stats(
            counter=[
                'm.api_log.test.test_hit',
            ],
        )

    def test_log_failure(self):
        self.provider.log_failure()
        self.check_stats(
            counter=[
                'm.api_log.test.test_miss',
            ],
        )


class TestAbstractCellLocationProvider(AbstractLocationProviderTest):

    class TestProvider(AbstractCellLocationProvider):
        model = Cell
        location_type = PositionLocation
        log_name = 'test'
        data_field = 'cell'

    def test_locate_with_no_data_returns_None(self):
        location = self.provider.locate({})
        self.assertFalse(location.found())

    def test_locate_finds_cell_with_same_cid(self):
        cell_key = {'mcc': GB_MCC, 'mnc': 1, 'lac': 1}
        self.session.add(self.TestProvider.model(
            lat=GB_LAT, lon=GB_LON, range=6000,
            radio=Radio.gsm, cid=1, **cell_key))
        self.session.flush()

        location = self.provider.locate(
            {'cell': [dict(cid=1, radio=Radio.gsm.name, **cell_key)]})
        self.assertEqual(type(location), PositionLocation)
        self.assertEqual(location.lat, GB_LAT)
        self.assertEqual(location.lon, GB_LON)
        self.assertEqual(location.accuracy, 6000)

    def test_locate_fails_to_find_cell_with_wrong_cid(self):
        cell_key = {'mcc': GB_MCC, 'mnc': 1, 'lac': 1}
        self.session.add(self.TestProvider.model(
            lat=GB_LAT, lon=GB_LON, range=6000,
            radio=Radio.gsm, cid=1, **cell_key))
        self.session.flush()

        location = self.provider.locate(
            {'cell': [dict(cid=2, radio=Radio.gsm.name, **cell_key)]})
        self.assertFalse(location.found())

    def test_multiple_cells_combined(self):
        cell_key = {'mcc': GB_MCC, 'mnc': 1, 'lac': 1}
        self.session.add(self.TestProvider.model(
            lat=GB_LAT + 0.1, lon=GB_LON + 0.1, range=6000,
            radio=Radio.gsm, cid=1, **cell_key))
        self.session.add(self.TestProvider.model(
            lat=GB_LAT + 0.3, lon=GB_LON + 0.3, range=6000,
            radio=Radio.gsm, cid=2, **cell_key))
        self.session.flush()

        location = self.provider.locate({'cell': [
            dict(cid=1, radio=Radio.gsm.name, **cell_key),
            dict(cid=2, radio=Radio.gsm.name, **cell_key),
        ]})
        self.assertEqual(type(location), PositionLocation)
        self.assertEqual(location.lat, GB_LAT + 0.2)
        self.assertEqual(location.lon, GB_LON + 0.2)


class TestAbstractCellAreaLocationProvider(AbstractLocationProviderTest):

    class TestProvider(AbstractCellAreaLocationProvider):
        model = CellArea
        location_type = PositionLocation
        log_name = 'cell_lac'
        data_field = 'cell'

    def test_shortest_range_lac_used(self):
        cell_key = {'mcc': GB_MCC, 'mnc': 1}
        self.session.add(self.TestProvider.model(
            lat=GB_LAT, lon=GB_LON, range=25000,
            radio=Radio.gsm, lac=1, **cell_key))
        self.session.add(self.TestProvider.model(
            lat=GB_LAT, lon=GB_LON, range=30000,
            radio=Radio.gsm, lac=2, **cell_key))
        self.session.flush()

        location = self.provider.locate({'cell': [
            dict(radio=Radio.gsm.name, lac=1, cid=1, **cell_key),
            dict(radio=Radio.gsm.name, lac=2, cid=1, **cell_key),
        ]})
        self.assertEqual(type(location), PositionLocation)
        self.assertEqual(location.lat, GB_LAT)
        self.assertEqual(location.lon, GB_LON)
        self.assertEqual(location.accuracy, 25000)

    def test_minimum_range_returned(self):
        cell_key = {'mcc': GB_MCC, 'mnc': 1}
        self.session.add(self.TestProvider.model(
            lat=GB_LAT, lon=GB_LON, range=15000,
            radio=Radio.gsm, lac=1, **cell_key))
        self.session.add(self.TestProvider.model(
            lat=GB_LAT, lon=GB_LON, range=30000,
            radio=Radio.gsm, lac=2, **cell_key))
        self.session.flush()

        location = self.provider.locate({'cell': [
            dict(radio=Radio.gsm.name, lac=1, cid=1, **cell_key),
            dict(radio=Radio.gsm.name, lac=2, cid=1, **cell_key),
        ]})
        self.assertEqual(type(location), PositionLocation)
        self.assertEqual(location.lat, GB_LAT)
        self.assertEqual(location.lon, GB_LON)
        self.assertEqual(location.accuracy, LAC_MIN_ACCURACY)


class TestCellCountryProvider(AbstractLocationProviderTest):

    TestProvider = CellCountryProvider

    def test_locate_finds_country_from_mcc(self):
        mcc = 302
        country = mobile_codes.mcc(str(mcc))[0]
        cell_key = {'mcc': mcc, 'mnc': 1, 'lac': 1}
        location = self.provider.locate(
            {'cell': [dict(cid=1, radio=Radio.gsm.name, **cell_key)]})
        self.assertEqual(type(location), CountryLocation)
        self.assertEqual(location.country_code, country.alpha2)
        self.assertEqual(location.country_name, country.name)

    def test_mcc_with_multiple_countries_returns_empty_location(self):
        mcc = 310
        country = mobile_codes.mcc(str(mcc))
        cell_key = {'mcc': mcc, 'mnc': 1, 'lac': 1}
        location = self.provider.locate(
            {'cell': [dict(cid=1, radio=Radio.gsm.name, **cell_key)]})
        self.assertEqual(type(location), CountryLocation)
        self.assertFalse(location.found())


class TestWifiLocationProvider(AbstractLocationProviderTest):

    TestProvider = WifiLocationProvider

    def test_wifi(self):
        wifis = [{'key': '001122334455'}, {'key': '112233445566'}]
        self.session.add(Wifi(
            key=wifis[0]['key'], lat=GB_LAT, lon=GB_LON, range=200))
        self.session.add(Wifi(
            key=wifis[1]['key'], lat=GB_LAT, lon=GB_LON + 0.00001, range=300))
        self.session.flush()

        location = self.provider.locate({'wifi': wifis})
        self.assertEqual(location.lat, GB_LAT)
        self.assertEqual(location.lon, GB_LON + 0.000005)
        self.assertEqual(location.accuracy, WIFI_MIN_ACCURACY)

        self.check_stats(
            timer=[
                'm.wifi.provided',
            ],
        )

    def test_wifi_too_few_candidates(self):
        wifis = [
            Wifi(key='001122334455', lat=1.0, lon=1.0),
            Wifi(key='112233445566', lat=1.001, lon=1.002),
        ]
        self.session.add_all(wifis)
        self.session.flush()

        location = self.provider.locate({'wifi': [{'key': '001122334455'}]})
        self.assertFalse(location.found())
        self.check_stats(
            counter=[
                'm.wifi.provided_too_few',
            ],
        )

    def test_wifi_too_few_matches(self):
        wifis = [
            Wifi(key='001122334455', lat=1.0, lon=1.0),
            Wifi(key='112233445566', lat=1.001, lon=1.002),
            Wifi(key='223344556677', lat=None, lon=None),
        ]
        self.session.add_all(wifis)
        self.session.flush()

        location = self.provider.locate({'wifi': [{'key': '001122334455'}, {'key': '223344556677'}]})
        self.assertFalse(location.found())
        self.check_stats(
            counter=[
                'm.wifi.found_too_few',
                'm.wifi.partial_match',
            ],
            timer=[
                'm.wifi.provided_not_known',
            ],
        )

    def test_wifi_too_similar_bssids_by_arithmetic_difference(self):
        wifis = [
            Wifi(key='00000000001f', lat=1.0, lon=1.0),
            Wifi(key='000000000020', lat=1.0, lon=1.0),
        ]
        self.session.add_all(wifis)
        self.session.flush()

        location = self.provider.locate({'wifi': [{'key': '00000000001f'}, {'key': '000000000020'}]})
        self.assertFalse(location.found())
        self.check_stats(
            timer=[
                'm.wifi.provided_too_similar',
            ],
        )

    def test_wifi_too_similar_bssids_by_hamming_distance(self):
        wifis = [
            Wifi(key='000000000058', lat=1.0, lon=1.0),
            Wifi(key='00000000005c', lat=1.0, lon=1.0),
        ]
        self.session.add_all(wifis)
        self.session.flush()

        location = self.provider.locate({'wifi': [{'key': '000000000058'}, {'key': '00000000005c'}]})
        self.assertFalse(location.found())
        self.check_stats(
            timer=[
                'm.wifi.provided_too_similar',
            ],
        )

    def test_wifi_similar_bssids_but_enough_clusters(self):
        wifis = [
            Wifi(key='00000000001f', lat=1.0, lon=1.0),
            Wifi(key='000000000020', lat=1.0, lon=1.0),
            Wifi(key='000000000058', lat=1.00004, lon=1.00004),
            Wifi(key='00000000005c', lat=1.00004, lon=1.00004),
        ]
        self.session.add_all(wifis)
        self.session.flush()

        location = self.provider.locate({'wifi': [{'key': '00000000001f'},
                           {'key': '000000000020'},
                           {'key': '000000000058'},
                           {'key': '00000000005c'}]})
        self.assertEqual(location.lat, 1.00002)
        self.assertEqual(location.lon, 1.00002)
        self.assertEqual(location.accuracy, 100.0)

    def test_wifi_similar_bssids_but_enough_found_clusters(self):
        wifis = [
            Wifi(key='00000000001f', lat=1.0, lon=1.0),
            Wifi(key='000000000024', lat=1.00004, lon=1.00004),
        ]
        self.session.add_all(wifis)
        self.session.flush()

        location = self.provider.locate({'wifi': [{'key': '00000000001f'},
                           {'key': '000000000020'},
                           {'key': '000000000021'},
                           {'key': '000000000022'},
                           {'key': '000000000023'},
                           {'key': '000000000024'}]})
        self.assertEqual(location.lat, 1.00002)
        self.assertEqual(location.lon, 1.00002)
        self.assertEqual(location.accuracy, 100.0)

    def test_wifi_ignore_outlier(self):
        wifis = [
            Wifi(key='001122334455', lat=1.0, lon=1.0),
            Wifi(key='112233445566', lat=1.001, lon=1.002),
            Wifi(key='223344556677', lat=1.002, lon=1.004),
            Wifi(key='334455667788', lat=2.0, lon=2.0),
        ]
        self.session.add_all(wifis)
        self.session.flush()

        location = self.provider.locate({
            'wifi': [
                {'key': '001122334455'}, {'key': '112233445566'},
                {'key': '223344556677'}, {'key': '334455667788'},
            ]})
        self.assertEqual(location.lat, 1.001)
        self.assertEqual(location.lon, 1.002)
        self.assertEqual(location.accuracy, 248.6090897)

    def test_wifi_prefer_cluster_with_better_signals(self):
        wifis = [
            Wifi(key='a1' * 6, lat=1.0, lon=1.0),
            Wifi(key='b2' * 6, lat=1.001, lon=1.002),
            Wifi(key='c3' * 6, lat=1.002, lon=1.004),
            Wifi(key='d4' * 6, lat=2.0, lon=2.0),
            Wifi(key='e5' * 6, lat=2.001, lon=2.002),
            Wifi(key='f6' * 6, lat=2.002, lon=2.004),
        ]
        self.session.add_all(wifis)
        self.session.flush()

        location = self.provider.locate({
            'wifi': [
                {'key': 'A1' * 6, 'signal': -100},
                {'key': 'D4' * 6, 'signal': -80},
                {'key': 'B2' * 6, 'signal': -100},
                {'key': 'E5' * 6, 'signal': -90},
                {'key': 'C3' * 6, 'signal': -100},
                {'key': 'F6' * 6, 'signal': -54},
            ]})
        self.assertEqual(location.lat, 2.001)
        self.assertEqual(location.lon, 2.002)
        self.assertEqual(location.accuracy, 248.51819)

    def test_wifi_prefer_larger_cluster_over_high_signal(self):
        wifis = [Wifi(key=('0%X' % i).lower() * 6,
                      lat=1 + i * 0.000010,
                      lon=1 + i * 0.000012)
                 for i in range(1, 6)]
        wifis += [
            Wifi(key='d4' * 6, lat=2.0, lon=2.0),
            Wifi(key='e5' * 6, lat=2.001, lon=2.002),
            Wifi(key='f6' * 6, lat=2.002, lon=2.004),
        ]
        self.session.add_all(wifis)
        self.session.flush()

        observations = [dict(key=('0%X' % i) * 6,
                             signal=-80)
                        for i in range(1, 6)]
        observations += [
            dict(key='D4' * 6, signal=-75),
            dict(key='E5' * 6, signal=-74),
            dict(key='F6' * 6, signal=-73)
        ]
        random.shuffle(observations)

        location = self.provider.locate({'wifi': observations})
        self.assertEqual(location.lat, 1.00003)
        self.assertEqual(location.lon, 1.000036)
        self.assertEqual(location.accuracy, WIFI_MIN_ACCURACY)

    def test_wifi_only_use_top_five_signals_in_noisy_cluster(self):
        # all these should wind up in the same cluster since
        # clustering threshold is 500m and the 10 wifis are
        # spaced in increments of (+1m, +1.2m)
        wifis = [Wifi(key=('0%X'.lower() % i) * 6,
                      lat=1 + i * 0.000010,
                      lon=1 + i * 0.000012)
                 for i in range(1, 11)]
        self.session.add_all(wifis)
        self.session.commit()
        observations = [dict(key=('0%X' % i) * 6,
                             signal=-80)
                        for i in range(6, 11)]
        observations += [
            dict(key='010101010101', signal=-75),
            dict(key='020202020202', signal=-74),
            dict(key='030303030303', signal=-73),
            dict(key='040404040404', signal=-72),
            dict(key='050505050505', signal=-71),
        ]
        random.shuffle(observations)

        location = self.provider.locate({'wifi': observations})
        self.assertEqual(location.lat, 1.00003)
        self.assertEqual(location.lon, 1.000036)
        self.assertEqual(location.accuracy, WIFI_MIN_ACCURACY)

    def test_wifi_not_closeby(self):
        wifis = [
            Wifi(key='101010101010', lat=1.0, lon=1.0),
            Wifi(key='202020202020', lat=1.001, lon=1.002),
            Wifi(key='303030303030', lat=2.002, lon=2.004),
            Wifi(key='404040404040', lat=2.0, lon=2.0),
        ]
        self.session.add_all(wifis)
        self.session.flush()

        location = self.provider.locate({'wifi': [{'key': '101010101010'}, {'key': '303030303030'}]})
        self.assertFalse(location.found())
