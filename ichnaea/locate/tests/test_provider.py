import mobile_codes
import random

import mock
import requests_mock
import simplejson as json
from redis import ConnectionError
from requests.exceptions import RequestException

from ichnaea.constants import (
    LAC_MIN_ACCURACY,
    WIFI_MIN_ACCURACY,
)
from ichnaea.locate.location import (
    EmptyLocation,
    Country,
    Position,
)
from ichnaea.locate.provider import (
    CellAreaPositionProvider,
    CellCountryProvider,
    CellPositionProvider,
    DataSource,
    FallbackProvider,
    GeoIPCountryProvider,
    GeoIPPositionProvider,
    Provider,
    WifiPositionProvider,
)
from ichnaea.models import (
    ApiKey,
    Radio,
    Wifi,
)
from ichnaea.tests.base import (
    CANADA_MCC,
    DBTestCase,
    GeoIPIsolation,
    GB_LAT,
    GB_LON,
    GB_MCC,
    USA_MCC,
    RedisIsolation,
)
from ichnaea.tests.factories import CellFactory, WifiFactory


class ProviderTest(GeoIPIsolation, RedisIsolation, DBTestCase):

    default_session = 'db_ro_session'
    settings = {}

    class TestProvider(Provider):
        location_type = Position
        log_name = 'test'

    def setUp(self):
        super(ProviderTest, self).setUp()

        self.provider = self.TestProvider(
            session_db=self.session,
            geoip_db=self.geoip_db,
            redis_client=self.redis_client,
            settings=self.settings,
            api_key=ApiKey(shortname='test', log=True),
            api_name='m',
        )


class TestProvider(ProviderTest):

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


class TestCellPositionProvider(ProviderTest):

    TestProvider = CellPositionProvider

    def test_locate_with_no_data_returns_none(self):
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
        self.assertEqual(type(location), Position)
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
        self.assertTrue(location.query_data)

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
        self.assertEqual(type(location), Position)
        self.assertEqual(location.lat, GB_LAT + 0.2)
        self.assertEqual(location.lon, GB_LON + 0.2)


class TestCellAreaPositionProvider(ProviderTest):

    TestProvider = CellAreaPositionProvider

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
        self.assertEqual(type(location), Position)
        self.assertEqual(location.lat, GB_LAT)
        self.assertEqual(location.lon, GB_LON)
        self.assertEqual(location.accuracy, 25000)

    def test_minimum_range_returned(self):
        cell_key = {'mcc': GB_MCC, 'mnc': 1}
        self.session.add(self.TestProvider.model(
            lat=GB_LAT, lon=GB_LON, range=LAC_MIN_ACCURACY - 2000,
            radio=Radio.gsm, lac=1, **cell_key))
        self.session.add(self.TestProvider.model(
            lat=GB_LAT, lon=GB_LON, range=LAC_MIN_ACCURACY + 3000,
            radio=Radio.gsm, lac=2, **cell_key))
        self.session.flush()

        location = self.provider.locate({'cell': [
            dict(radio=Radio.gsm.name, lac=1, cid=1, **cell_key),
            dict(radio=Radio.gsm.name, lac=2, cid=1, **cell_key),
        ]})
        self.assertEqual(type(location), Position)
        self.assertEqual(location.lat, GB_LAT)
        self.assertEqual(location.lon, GB_LON)
        self.assertEqual(location.accuracy, LAC_MIN_ACCURACY)


class TestCellCountryProvider(ProviderTest):

    TestProvider = CellCountryProvider

    def test_locate_finds_country_from_mcc(self):
        country = mobile_codes.mcc(str(CANADA_MCC))[0]
        cell_key = {'mcc': CANADA_MCC, 'mnc': 1, 'lac': 1}
        location = self.provider.locate(
            {'cell': [dict(cid=1, radio=Radio.gsm.name, **cell_key)]})
        self.assertEqual(type(location), Country)
        self.assertEqual(location.country_code, country.alpha2)
        self.assertEqual(location.country_name, country.name)

    def test_mcc_with_multiple_countries_returns_empty_location(self):
        cell_key = {'mcc': USA_MCC, 'mnc': 1, 'lac': 1}
        location = self.provider.locate(
            {'cell': [dict(cid=1, radio=Radio.gsm.name, **cell_key)]})
        self.assertEqual(type(location), Country)
        self.assertFalse(location.found())
        self.assertTrue(location.query_data)


class TestWifiPositionProvider(ProviderTest):

    TestProvider = WifiPositionProvider

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

    def test_wifi_too_few_candidates(self):
        wifis = [
            Wifi(key='001122334455', lat=1.0, lon=1.0),
            Wifi(key='112233445566', lat=1.001, lon=1.002),
        ]
        self.session.add_all(wifis)
        self.session.flush()

        location = self.provider.locate({'wifi': [{'key': '001122334455'}]})
        self.assertFalse(location.found())
        self.assertFalse(location.query_data)

    def test_wifi_too_few_matches(self):
        wifis = [
            Wifi(key='001122334455', lat=1.0, lon=1.0),
            Wifi(key='112233445566', lat=1.001, lon=1.002),
            Wifi(key='223344556677', lat=None, lon=None),
        ]
        self.session.add_all(wifis)
        self.session.flush()

        location = self.provider.locate(
            {'wifi': [{'key': '001122334455'}, {'key': '223344556677'}]})
        self.assertFalse(location.found())
        self.assertTrue(location.query_data)

    def test_wifi_too_similar_bssids_by_arithmetic_difference(self):
        wifis = [
            Wifi(key='00000000001f', lat=1.0, lon=1.0),
            Wifi(key='000000000020', lat=1.0, lon=1.0),
        ]
        self.session.add_all(wifis)
        self.session.flush()

        location = self.provider.locate(
            {'wifi': [{'key': '00000000001f'}, {'key': '000000000020'}]})
        self.assertFalse(location.found())
        self.assertFalse(location.query_data)

    def test_wifi_too_similar_bssids_by_hamming_distance(self):
        wifis = [
            Wifi(key='000000000058', lat=1.0, lon=1.0),
            Wifi(key='00000000005c', lat=1.0, lon=1.0),
        ]
        self.session.add_all(wifis)
        self.session.flush()

        location = self.provider.locate(
            {'wifi': [{'key': '000000000058'}, {'key': '00000000005c'}]})
        self.assertFalse(location.found())
        self.assertFalse(location.query_data)

    def test_wifi_similar_bssids_but_enough_clusters(self):
        wifis = [
            Wifi(key='00000000001f', lat=1.0, lon=1.0),
            Wifi(key='000000000020', lat=1.0, lon=1.0),
            Wifi(key='000000000058', lat=1.00004, lon=1.00004),
            Wifi(key='00000000005c', lat=1.00004, lon=1.00004),
        ]
        self.session.add_all(wifis)
        self.session.flush()

        location = self.provider.locate({'wifi': [
            {'key': '00000000001f'},
            {'key': '000000000020'},
            {'key': '000000000058'},
            {'key': '00000000005c'},
        ]})
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

        location = self.provider.locate({'wifi': [
            {'key': '00000000001f'},
            {'key': '000000000020'},
            {'key': '000000000021'},
            {'key': '000000000022'},
            {'key': '000000000023'},
            {'key': '000000000024'},
        ]})
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

        location = self.provider.locate(
            {'wifi': [{'key': '101010101010'}, {'key': '303030303030'}]})
        self.assertFalse(location.found())
        self.assertTrue(location.query_data)


class TestGeoIPPositionProvider(ProviderTest):

    TestProvider = GeoIPPositionProvider

    def test_geoip_unknown(self):
        location = self.provider.locate({'geoip': '127.0.0.1'})
        self.assertEqual(type(location), Position)
        self.assertFalse(location.found())
        self.assertTrue(location.query_data)

    def test_geoip_city(self):
        london = self.geoip_data['London']
        location = self.provider.locate({'geoip': london['ip']})
        self.assertEqual(type(location), Position)
        self.assertEqual(location.lat, london['latitude'])
        self.assertEqual(location.lon, london['longitude'])
        self.assertEqual(location.accuracy, london['accuracy'])

    def test_geoip_country(self):
        bhutan = self.geoip_data['Bhutan']
        location = self.provider.locate({'geoip': bhutan['ip']})
        self.assertEqual(type(location), Position)
        self.assertEqual(location.lat, bhutan['latitude'])
        self.assertEqual(location.lon, bhutan['longitude'])
        self.assertEqual(location.accuracy, bhutan['accuracy'])


class TestGeoIPCountryProvider(ProviderTest):

    TestProvider = GeoIPCountryProvider

    def test_geoip_unknown(self):
        location = self.provider.locate({'geoip': '127.0.0.1'})
        self.assertEqual(type(location), Country)
        self.assertFalse(location.found())
        self.assertTrue(location.query_data)

    def test_geoip_country(self):
        bhutan = self.geoip_data['Bhutan']
        location = self.provider.locate({'geoip': bhutan['ip']})
        self.assertEqual(type(location), Country)
        self.assertEqual(location.country_code, bhutan['country_code'])
        self.assertEqual(location.country_name, bhutan['country_name'])


class TestFallbackProvider(ProviderTest):

    TestProvider = FallbackProvider
    settings = {
        'url': 'http://127.0.0.1:9/?api',
        'ratelimit': '10',
        'ratelimit_expire': '60',
        'cache_expire': '60',
    }

    def setUp(self):
        super(TestFallbackProvider, self).setUp()

        self.provider.api_key.allow_fallback = True

        self.response_location = {
            'location': {
                'lat': 51.5366,
                'lng': 0.03989,
            },
            'accuracy': 1500,
            'fallback': 'lacf',
        }

        self.cells = []
        for cell in CellFactory.build_batch(2):
            self.cells.append({
                'radio': cell.radio,
                'mcc': cell.mcc,
                'mnc': cell.mnc,
                'lac': cell.lac,
                'cid': cell.cid,
                'signal': -70,
            })
        self.cells[0]['ta'] = 1

        self.wifis = []
        for wifi in WifiFactory.build_batch(2):
            self.wifis.append({
                'key': wifi.key,
                'signal': -77,
            })
        self.wifis[0]['channel'] = 6
        self.wifis[0]['frequency'] = 2437
        self.wifis[0]['snr'] = 13

    def test_successful_call_returns_location(self):
        with requests_mock.Mocker() as mock_request:
            mock_request.register_uri(
                'POST', requests_mock.ANY, json=self.response_location)

            location = self.provider.locate({
                'cell': self.cells,
                'wifi': self.wifis,
            })

        self.assertTrue(location.found())
        self.assertEqual(
            location.lat, self.response_location['location']['lat'])
        self.assertEqual(
            location.lon, self.response_location['location']['lng'])
        self.assertEqual(
            location.accuracy, self.response_location['accuracy'])
        self.check_raven(total=0)
        self.check_stats(
            counter=['m.fallback.lookup_status.200'],
            timer=['m.fallback.lookup'])

    def test_failed_call_returns_empty_location(self):
        with requests_mock.Mocker() as mock_request:
            def raise_request_exception(request, context):
                raise RequestException()

            mock_request.register_uri(
                'POST', requests_mock.ANY, json=raise_request_exception)

            location = self.provider.locate({
                'cell': self.cells,
                'wifi': self.wifis,
            })

        self.assertFalse(location.found())

    def test_invalid_json_returns_empty_location(self):
        with requests_mock.Mocker() as mock_request:
            mock_request.register_uri(
                'POST', requests_mock.ANY, json='[invalid json')

            location = self.provider.locate({
                'cell': self.cells,
                'wifi': self.wifis,
            })

        self.assertFalse(location.found())

    def test_403_response_returns_empty_location(self):
        with requests_mock.Mocker() as mock_request:
            mock_request.register_uri(
                'POST', requests_mock.ANY, status_code=403)

            location = self.provider.locate({
                'cell': self.cells,
                'wifi': self.wifis,
            })

        self.assertFalse(location.found())
        self.check_raven([('HTTPError', 1)])
        self.check_stats(counter=['m.fallback.lookup_status.403'])

    def test_404_response_returns_empty_location(self):
        response_json = {
            'error': {
                'errors': {
                    'domain': 'geolocation',
                    'reason': 'notFound',
                    'message': 'Not Found',
                },
                'code': 404,
                'message': 'Not Found'
            }
        }

        with requests_mock.Mocker() as mock_request:
            mock_request.register_uri(
                'POST', requests_mock.ANY,
                json=response_json,
                status_code=404)

            location = self.provider.locate({
                'cell': self.cells,
                'wifi': self.wifis,
            })

        self.assertFalse(location.found())
        self.check_raven([('HTTPError', 0)])
        self.check_stats(counter=['m.fallback.lookup_status.404'])

    def test_500_response_returns_empty_location(self):
        with requests_mock.Mocker() as mock_request:
            mock_request.register_uri(
                'POST', requests_mock.ANY, status_code=500)

            location = self.provider.locate({
                'cell': self.cells,
                'wifi': self.wifis,
            })

        self.assertFalse(location.found())
        self.check_raven([('HTTPError', 1)])
        self.check_stats(
            counter=['m.fallback.lookup_status.500'],
            timer=['m.fallback.lookup'])

    def test_no_call_made_when_not_allowed_for_apikey(self):
        self.provider.api_key.allow_fallback = False

        query_data = {
            'cell': self.cells,
            'wifi': self.wifis,
        }
        location = EmptyLocation()

        self.assertFalse(self.provider.should_locate(query_data, location))

    def test_should_not_provide_location_if_one_wifi_provided(self):
        self.assertFalse(self.provider.should_locate({
            'cell': [],
            'wifi': self.wifis[:1],
        }, EmptyLocation()))

    def test_should_not_provide_location_without_cell_or_wifi_data(self):
        self.assertFalse(self.provider.should_locate({}, EmptyLocation()))

    def test_should_not_provide_location_if_malformed_cell(self):
        malformed_cell = CellFactory.build(mcc=99999)
        self.assertFalse(self.provider.should_locate({
            'cell': [malformed_cell],
            'wifi': [],
        }, EmptyLocation()))

    def test_should_not_provide_location_if_malformed_wifi(self):
        malformed_wifi = {'key': 'abcd'}
        self.assertFalse(self.provider.should_locate({
            'cell': [],
            'wifi': [self.wifis[0], malformed_wifi],
        }, EmptyLocation()))

    def test_should_provide_location_if_only_empty_location_found(self):
        self.assertTrue(self.provider.should_locate({
            'cell': [],
            'wifi': self.wifis,
        }, EmptyLocation()))

    def test_should_provide_location_if_only_geoip_location_found(self):
        london = self.geoip_data['London']
        geoip_location = Position(
            source=DataSource.GeoIP,
            lat=london['latitude'],
            lon=london['longitude'],
            accuracy=london['accuracy'],
        )

        query_data = {
            'cell': [],
            'geoip': london['ip'],
            'wifi': self.wifis,
        }

        self.assertTrue(
            self.provider.should_locate(query_data, geoip_location))

    def test_should_not_provide_location_if_non_geoip_location_found(self):
        internal_location = Position(
            source=DataSource.Internal, lat=1.0, lon=1.0, accuracy=1.0)

        query_data = {
            'cell': [],
            'wifi': self.wifis,
        }

        self.assertFalse(
            self.provider.should_locate(query_data, internal_location))

    def test_rate_limiting_allows_calls_below_ratelimit(self):
        with requests_mock.Mocker() as mock_request:
            mock_request.register_uri(
                'POST', requests_mock.ANY, json=self.response_location)

            for _ in range(self.provider.ratelimit):
                location = self.provider.locate({
                    'cell': self.cells,
                    'wifi': self.wifis,
                })

                self.assertTrue(location.found())

    def test_rate_limiting_blocks_calls_above_ratelimit(self):
        with requests_mock.Mocker() as mock_request:
            mock_request.register_uri(
                'POST', requests_mock.ANY, json=self.response_location)

            ratelimit_key = self.provider.get_ratelimit_key()
            self.redis_client.set(ratelimit_key, self.provider.ratelimit)

            location = self.provider.locate({
                'cell': self.cells,
                'wifi': self.wifis,
            })

            self.assertFalse(location.found())

    def test_redis_failure_during_ratelimit_prevents_external_call(self):
        mock_redis_client = mock.Mock()
        mock_redis_client.pipeline.side_effect = ConnectionError()
        self.provider.redis_client = mock_redis_client

        with requests_mock.Mocker() as mock_request:
            mock_request.register_uri(
                'POST', requests_mock.ANY, json=self.response_location)

            location = self.provider.locate({
                'cell': self.cells[:1],
                'wifi': [],
            })

            self.assertFalse(mock_request.called)
            self.assertFalse(location.found())

    def test_redis_failure_during_get_cache_allows_external_call(self):
        mock_redis_client = mock.Mock()
        mock_redis_client.pipeline.return_value = mock.Mock()
        mock_redis_client.pipeline.return_value.__enter__ = mock.Mock()
        mock_redis_client.pipeline.return_value.__exit__ = mock.Mock()
        mock_redis_client.get.side_effect = ConnectionError()
        self.provider.redis_client = mock_redis_client

        with requests_mock.Mocker() as mock_request:
            mock_request.register_uri(
                'POST', requests_mock.ANY, json=self.response_location)

            location = self.provider.locate({
                'cell': self.cells[:1],
                'wifi': [],
            })

            self.assertTrue(mock_request.called)
            self.assertTrue(location.found())

    def test_redis_failure_during_set_cache_returns_location(self):
        mock_redis_client = mock.Mock()
        mock_redis_client.pipeline.return_value = mock.Mock()
        mock_redis_client.pipeline.return_value.__enter__ = mock.Mock()
        mock_redis_client.pipeline.return_value.__exit__ = mock.Mock()
        mock_redis_client.get.return_value = None
        mock_redis_client.set.side_effect = ConnectionError()
        self.provider.redis_client = mock_redis_client

        with requests_mock.Mocker() as mock_request:
            mock_request.register_uri(
                'POST', requests_mock.ANY, json=self.response_location)

            location = self.provider.locate({
                'cell': self.cells[:1],
                'wifi': [],
            })

            self.assertTrue(mock_request.called)
            self.assertTrue(location.found())

    def test_single_cell_results_cached_preventing_external_call(self):
        with requests_mock.Mocker() as mock_request:
            mock_request.register_uri(
                'POST', requests_mock.ANY, json=self.response_location)

            location = self.provider.locate({
                'cell': self.cells[:1],
                'wifi': [],
            })

            self.assertTrue(location.found())
            self.assertEqual(mock_request.call_count, 1)
            self.assertEqual(
                location.lat, self.response_location['location']['lat'])
            self.assertEqual(
                location.lon, self.response_location['location']['lng'])
            self.assertEqual(
                location.accuracy, self.response_location['accuracy'])
            self.check_raven(total=0)
            self.check_stats(
                counter=[
                    'm.fallback.lookup_status.200',
                    'm.fallback.cache.miss',
                ],
                timer=['m.fallback.lookup'])

            location = self.provider.locate({
                'cell': self.cells[:1],
                'wifi': [],
            })

            self.assertTrue(location.found())
            self.assertEqual(mock_request.call_count, 1)
            self.assertEqual(
                location.lat, self.response_location['location']['lat'])
            self.assertEqual(
                location.lon, self.response_location['location']['lng'])
            self.assertEqual(
                location.accuracy, self.response_location['accuracy'])
            self.check_stats(
                counter=[
                    'm.fallback.lookup_status.200',
                    'm.fallback.cache.hit',
                ],
                timer=['m.fallback.lookup'])

    def test_empty_result_from_fallback_cached(self):
        with requests_mock.Mocker() as mock_request:
            error_response = {
                'error': {
                    'code': 404,
                    'errors': {
                        'domain': '',
                        'message': '',
                        'reason': '',
                    },
                    'message': '',
                }
            }

            mock_request.register_uri(
                'POST',
                requests_mock.ANY,
                json=error_response,
                status_code=404
            )

            location = self.provider.locate({
                'cell': self.cells[:1],
                'wifi': [],
            })

            self.assertFalse(location.found())
            self.assertEqual(mock_request.call_count, 1)
            self.check_stats(
                counter=[
                    'm.fallback.lookup_status.404',
                    'm.fallback.cache.miss',
                ],
                timer=['m.fallback.lookup'])

            location = self.provider.locate({
                'cell': self.cells[:1],
                'wifi': [],
            })

            self.assertFalse(location.found())
            self.assertEqual(mock_request.call_count, 1)
            self.check_stats(
                counter=[
                    'm.fallback.lookup_status.404',
                    'm.fallback.cache.hit',
                ],
                timer=['m.fallback.lookup'])

            self.check_raven(total=0)

    def test_dont_set_cache_value_retrieved_from_cache(self):
        mock_redis_client = mock.Mock()
        mock_redis_client.pipeline.return_value = mock.Mock()
        mock_redis_client.pipeline.return_value.__enter__ = mock.Mock()
        mock_redis_client.pipeline.return_value.__exit__ = mock.Mock()
        mock_redis_client.get.return_value = json.dumps(self.response_location)
        self.provider.redis_client = mock_redis_client

        with requests_mock.Mocker() as mock_request:
            mock_request.register_uri(
                'POST', requests_mock.ANY, json=self.response_location)

            location = self.provider.locate({
                'cell': self.cells[:1],
                'wifi': [],
            })

            self.assertTrue(location.found())
            self.assertFalse(mock_redis_client.set.called)

    def test_cache_expire_set_to_0_disables_caching(self):
        mock_redis_client = mock.Mock()
        mock_redis_client.pipeline.return_value = mock.Mock()
        mock_redis_client.pipeline.return_value.__enter__ = mock.Mock()
        mock_redis_client.pipeline.return_value.__exit__ = mock.Mock()
        mock_redis_client.get.return_value = json.dumps(self.response_location)
        self.provider.redis_client = mock_redis_client
        self.provider.cache_expire = 0

        with requests_mock.Mocker() as mock_request:
            mock_request.register_uri(
                'POST', requests_mock.ANY, json=self.response_location)

            location = self.provider.locate({
                'cell': self.cells[:1],
                'wifi': [],
            })

            self.assertTrue(location.found())
            self.assertFalse(mock_redis_client.get.called)
            self.assertFalse(mock_redis_client.set.called)

    def test_dont_cache_when_wifi_keys_present(self):
        mock_redis_client = mock.Mock()
        mock_redis_client.pipeline.return_value = mock.Mock()
        mock_redis_client.pipeline.return_value.__enter__ = mock.Mock()
        mock_redis_client.pipeline.return_value.__exit__ = mock.Mock()
        mock_redis_client.get.return_value = json.dumps(self.response_location)
        self.provider.redis_client = mock_redis_client

        with requests_mock.Mocker() as mock_request:
            mock_request.register_uri(
                'POST', requests_mock.ANY, json=self.response_location)

            location = self.provider.locate({
                'cell': self.cells[:1],
                'wifi': self.wifis,
            })

            self.assertTrue(location.found())
            self.assertFalse(mock_redis_client.get.called)
            self.assertFalse(mock_redis_client.set.called)
