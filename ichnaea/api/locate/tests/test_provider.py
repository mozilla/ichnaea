import mobile_codes
import random

import mock
import requests_mock
import simplejson as json
from redis import RedisError
from requests.exceptions import RequestException

from ichnaea.constants import (
    LAC_MIN_ACCURACY,
    WIFI_MIN_ACCURACY,
)
from ichnaea.api.exceptions import LocationNotFound
from ichnaea.api.locate.location import (
    EmptyLocation,
    Country,
    Position,
)
from ichnaea.api.locate.provider import (
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
from ichnaea.models import ApiKey
from ichnaea.tests.base import ConnectionTestCase
from ichnaea.tests.factories import (
    CellAreaFactory,
    CellFactory,
    WifiFactory,
)


class DummyModel(object):

    def __init__(self, lat=None, lon=None, accuracy=None,
                 alpha2=None, name=None, ip=None):
        self.lat = lat
        self.lon = lon
        self.range = accuracy
        self.alpha2 = alpha2
        self.name = name
        self.ip = ip


class ProviderTest(ConnectionTestCase):

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

    def model_query(self, cells=(), wifis=(), geoip=False, fallbacks=None):
        query = {}

        if cells:
            query['cell'] = []
            for cell in cells:
                cell_query = {
                    'radio': cell.radio,
                    'mcc': cell.mcc,
                    'mnc': cell.mnc,
                    'lac': cell.lac,
                }
                if getattr(cell, 'cid', None) is not None:
                    cell_query['cid'] = cell.cid
                query['cell'].append(cell_query)

        if wifis:
            query['wifi'] = []
            for wifi in wifis:
                query['wifi'].append({'key': wifi.key})

        if geoip:
            query['geoip'] = geoip

        if fallbacks:
            query['fallbacks'] = fallbacks

        return query

    def check_model_location(self, location, model, used=None, **kw):
        type_ = self.TestProvider.location_type
        if used is None:
            if model is None:
                self.assertFalse(location.query_data)
            else:
                self.assertTrue(location.query_data)
        else:
            self.assertIs(location.query_data, used)

        if not model:
            self.assertFalse(location.found())
            self.assertEqual(type(location), type_)
            return

        if type_ is Position:
            check_func = self.assertAlmostEqual
            expected = {
                'lat': kw.get('lat', model.lat),
                'lon': kw.get('lon', model.lon),
                'accuracy': kw.get('accuracy', model.range),
            }
        elif type_ is Country:
            check_func = self.assertEqual
            expected = {
                'country_code': model.alpha2,
                'country_name': model.name,
            }

        self.assertTrue(location.found())
        self.assertEqual(type(location), type_)
        for key, value in expected.items():
            check_func(getattr(location, key), value)

    def check_should_locate(self, query, should, location=None):
        if location is None:
            location = EmptyLocation()
        self.assertIs(self.provider.should_locate(query, location), should)


class GeoIPProviderTest(ProviderTest):

    @classmethod
    def setUpClass(cls):
        super(GeoIPProviderTest, cls).setUpClass()
        bhutan = cls.geoip_data['Bhutan']
        cls.bhutan_model = DummyModel(
            lat=bhutan['latitude'],
            lon=bhutan['longitude'],
            accuracy=bhutan['accuracy'],
            alpha2=bhutan['country_code'],
            name=bhutan['country_name'],
            ip=bhutan['ip'])
        london = cls.geoip_data['London']
        cls.london_model = DummyModel(
            lat=london['latitude'],
            lon=london['longitude'],
            accuracy=london['accuracy'],
            alpha2=london['country_code'],
            name=london['country_name'],
            ip=london['ip'])


class TestProvider(ProviderTest):

    def test_log_hit(self):
        self.provider.log_hit()
        self.check_stats(counter=[
            'm.test_hit',
        ])

    def test_log_success(self):
        self.provider.log_success()
        self.check_stats(counter=[
            'm.api_log.test.test_hit',
        ])

    def test_log_failure(self):
        self.provider.log_failure()
        self.check_stats(counter=[
            'm.api_log.test.test_miss',
        ])

    def test_should_locate_is_true_if_no_fallback_set(self):
        query = self.model_query(fallbacks={})
        self.check_should_locate(query, True)

    def test_should_not_locate_if_fallback_field_is_set(self):
        self.provider.fallback_field = 'fallback'
        query = self.model_query(fallbacks={'fallback': False})
        self.check_should_locate(query, False)

    def test_should_locate_if_a_different_fallback_field_is_set(self):
        self.provider.fallback_field = 'fallback'
        query = self.model_query(fallbacks={'another_fallback': False})
        self.check_should_locate(query, True)

    def test_should_locate_ignore_invalid_values(self):
        self.provider.fallback_field = 'fallback'
        query = self.model_query(fallbacks={'fallback': 'asdf'})
        self.check_should_locate(query, True)


class TestCellPositionProvider(ProviderTest):

    TestProvider = CellPositionProvider

    def test_locate_with_no_data_returns_none(self):
        query = self.model_query()
        location = self.provider.locate(query)
        self.check_model_location(location, None)

    def test_locate_finds_cell_with_same_cid(self):
        cell = CellFactory()
        self.session.flush()

        query = self.model_query(cells=[cell])
        location = self.provider.locate(query)
        self.check_model_location(location, cell)

    def test_locate_fails_to_find_cell_with_wrong_cid(self):
        cell = CellFactory()
        self.session.flush()
        cell.cid += 1

        query = self.model_query(cells=[cell])
        location = self.provider.locate(query)
        self.check_model_location(location, None, used=True)

    def test_multiple_cells_combined(self):
        cell = CellFactory()
        cell2 = CellFactory(radio=cell.radio, mcc=cell.mcc, mnc=cell.mnc,
                            lac=cell.lac, cid=cell.cid + 1,
                            lat=cell.lat + 0.02, lon=cell.lon + 0.02)
        self.session.flush()

        query = self.model_query(cells=[cell, cell2])
        location = self.provider.locate(query)
        self.check_model_location(
            location, cell,
            lat=cell.lat + 0.01, lon=cell.lon + 0.01)

    def test_no_db_query_for_incomplete_keys(self):
        cells = CellFactory.build_batch(5)
        cells[0].radio = None
        cells[1].mcc = None
        cells[2].mnc = None
        cells[3].lac = None
        cells[4].cid = None

        with self.db_call_checker() as check_db_calls:
            query = self.model_query(cells=cells)
            location = self.provider.locate(query)
            self.check_model_location(location, None)
            check_db_calls(rw=0, ro=0)


class TestCellAreaPositionProvider(ProviderTest):

    TestProvider = CellAreaPositionProvider

    def test_provider_should_not_locate_if_lacf_disabled(self):
        cells = CellFactory.build_batch(2)

        query = self.model_query(
            cells=cells,
            fallbacks={'lacf': False},
        )
        self.check_should_locate(query, False)

    def test_no_db_query_for_incomplete_keys(self):
        cells = CellFactory.build_batch(4)
        cells[0].radio = None
        cells[1].mcc = None
        cells[2].mnc = None
        cells[3].lac = None

        with self.db_call_checker() as check_db_calls:
            query = self.model_query(cells=cells)
            location = self.provider.locate(query)
            self.check_model_location(location, None)
            check_db_calls(rw=0, ro=0)

    def test_shortest_range_lac_used(self):
        area = CellAreaFactory(range=25000)
        area2 = CellAreaFactory(range=30000, lat=area.lat + 0.2)
        self.session.flush()

        query = self.model_query(cells=[area, area2])
        location = self.provider.locate(query)
        self.check_model_location(location, area)

    def test_minimum_range_returned(self):
        areas = CellAreaFactory.create_batch(2)
        areas[0].range = LAC_MIN_ACCURACY - 2000
        areas[1].range = LAC_MIN_ACCURACY + 3000
        areas[1].lat = areas[0].lat + 0.2
        self.session.flush()

        query = self.model_query(cells=areas)
        location = self.provider.locate(query)
        self.check_model_location(
            location, areas[0],
            accuracy=LAC_MIN_ACCURACY)


class TestCellCountryProvider(ProviderTest):

    TestProvider = CellCountryProvider

    def test_locate_finds_country_from_mcc(self):
        country = mobile_codes.mcc('235')[0]
        cell = CellFactory.build(mcc=235)

        query = self.model_query(cells=[cell])
        location = self.provider.locate(query)
        self.check_model_location(location, country)

    def test_mcc_with_multiple_countries_returns_empty_location(self):
        cell = CellFactory.build(mcc=234)

        query = self.model_query(cells=[cell])
        location = self.provider.locate(query)
        self.check_model_location(location, None, used=True)


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
        wifis = WifiFactory.create_batch(4)
        wifis[1].lat = wifis[0].lat + 0.0001
        wifis[1].lon = wifis[0].lon
        wifis[2].lat = wifis[0].lat + 0.0002
        wifis[2].lon = wifis[0].lon
        wifis[3].lat = wifis[0].lat + 1.0
        self.session.flush()

        query = self.model_query(wifis=wifis)
        location = self.provider.locate(query)
        self.check_model_location(
            location, wifis[0],
            lat=wifis[0].lat + 0.0001)

    def test_wifi_prefer_cluster_with_better_signals(self):
        wifi11 = WifiFactory()
        wifi12 = WifiFactory(lat=wifi11.lat + 0.0002, lon=wifi11.lon)
        wifi21 = WifiFactory(lat=wifi11.lat + 1.0, lon=wifi11.lon + 1.0)
        wifi22 = WifiFactory(lat=wifi21.lat + 0.0002, lon=wifi21.lon)
        self.session.flush()

        query = self.model_query(wifis=[wifi11, wifi12, wifi21, wifi22])
        query['wifi'][0]['signal'] = -100
        query['wifi'][1]['signal'] = -80
        query['wifi'][2]['signal'] = -100
        query['wifi'][3]['signal'] = -54
        location = self.provider.locate(query)
        self.check_model_location(
            location, wifi21,
            lat=wifi21.lat + 0.0001)

    def test_wifi_prefer_larger_cluster_over_high_signal(self):
        wifi = WifiFactory()
        wifis = WifiFactory.create_batch(3, lat=wifi.lat, lon=wifi.lon)
        wifis2 = WifiFactory.create_batch(3, lat=wifi.lat + 1.0, lon=wifi.lon)
        self.session.flush()

        query = self.model_query(wifis=[wifi] + wifis + wifis2)
        for entry in query['wifi'][:-3]:
            entry['signal'] = -80
        for entry in query['wifi'][-3:]:
            entry['signal'] = -70
        random.shuffle(query['wifi'])
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
        for i, entry in enumerate(query['wifi']):
            entry['signal'] = -70 - i
        random.shuffle(query['wifi'])
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


class TestGeoIPPositionProvider(GeoIPProviderTest):

    TestProvider = GeoIPPositionProvider

    def test_geoip_provider_should_not_locate_if_ipf_disabled(self):
        query = self.model_query(
            geoip='127.0.0.1',
            fallbacks={'ipf': False},
        )
        self.check_should_locate(query, False)

    def test_geoip_unknown(self):
        query = self.model_query(geoip='127.0.0.1')
        location = self.provider.locate(query)
        self.check_model_location(location, None, used=True)

    def test_geoip_city(self):
        query = self.model_query(geoip=self.london_model.ip)
        location = self.provider.locate(query)
        self.check_model_location(location, self.london_model)

    def test_geoip_country(self):
        query = self.model_query(geoip=self.bhutan_model.ip)
        location = self.provider.locate(query)
        self.check_model_location(location, self.bhutan_model)


class TestGeoIPCountryProvider(GeoIPProviderTest):

    TestProvider = GeoIPCountryProvider

    def test_geoip_unknown(self):
        query = self.model_query(geoip='127.0.0.1')
        location = self.provider.locate(query)
        self.check_model_location(location, None, used=True)

    def test_geoip_country(self):
        query = self.model_query(geoip=self.bhutan_model.ip)
        location = self.provider.locate(query)
        self.check_model_location(location, self.bhutan_model)


class TestFallbackProvider(GeoIPProviderTest):

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
        self.fallback_model = DummyModel(
            lat=51.5366, lon=0.03989, accuracy=1500)

        self.fallback_location = {
            'location': {
                'lat': self.fallback_model.lat,
                'lng': self.fallback_model.lon,
            },
            'accuracy': self.fallback_model.range,
            'fallback': 'lacf',
        }

    def _mock_redis_client(self):
        client = mock.Mock()
        client.pipeline.return_value = mock.Mock()
        client.pipeline.return_value.__enter__ = mock.Mock()
        client.pipeline.return_value.__exit__ = mock.Mock()
        client.get.return_value = mock.Mock()
        client.set.return_value = mock.Mock()
        return client

    def test_successful_call_returns_location(self):
        cell = CellFactory.build()

        with requests_mock.Mocker() as mock_request:
            mock_request.register_uri(
                'POST', requests_mock.ANY, json=self.fallback_location)

            query = self.model_query(
                cells=[cell],
                fallbacks={
                    'lacf': True,
                    'ipf': False,
                }
            )
            location = self.provider.locate(query)
            self.check_model_location(location, self.fallback_model)

            request_json = mock_request.request_history[0].json()

        self.assertEqual(request_json['fallbacks'], {'lacf': True})
        self.check_stats(
            counter=['m.fallback.lookup_status.200'],
            timer=['m.fallback.lookup'])

    def test_failed_call_returns_empty_location(self):
        cell = CellFactory.build()

        with requests_mock.Mocker() as mock_request:
            def raise_request_exception(request, context):
                raise RequestException()

            mock_request.register_uri(
                'POST', requests_mock.ANY, json=raise_request_exception)

            query = self.model_query(cells=[cell])
            location = self.provider.locate(query)
            self.check_model_location(location, None)

    def test_invalid_json_returns_empty_location(self):
        cell = CellFactory.build()

        with requests_mock.Mocker() as mock_request:
            mock_request.register_uri(
                'POST', requests_mock.ANY, json=['invalid json'])

            query = self.model_query(cells=[cell])
            location = self.provider.locate(query)
            self.check_model_location(location, None)

    def test_malformed_json_returns_empty_location(self):
        cell = CellFactory.build()

        with requests_mock.Mocker() as mock_request:
            mock_request.register_uri(
                'POST', requests_mock.ANY, content=b'[invalid json')

            query = self.model_query(cells=[cell])
            location = self.provider.locate(query)
            self.check_model_location(location, None)

    def test_403_response_returns_empty_location(self):
        cell = CellFactory.build()

        with requests_mock.Mocker() as mock_request:
            mock_request.register_uri(
                'POST', requests_mock.ANY, status_code=403)

            query = self.model_query(cells=[cell])
            location = self.provider.locate(query)
            self.check_model_location(location, None)

        self.check_raven([('HTTPError', 1)])
        self.check_stats(counter=['m.fallback.lookup_status.403'])

    def test_404_response_returns_empty_location(self):
        cell = CellFactory.build()

        with requests_mock.Mocker() as mock_request:
            mock_request.register_uri(
                'POST', requests_mock.ANY,
                json=LocationNotFound.json_body(),
                status_code=404)

            query = self.model_query(cells=[cell])
            location = self.provider.locate(query)
            self.check_model_location(location, None)

        self.check_raven([('HTTPError', 0)])
        self.check_stats(counter=['m.fallback.lookup_status.404'])

    def test_500_response_returns_empty_location(self):
        cell = CellFactory.build()

        with requests_mock.Mocker() as mock_request:
            mock_request.register_uri(
                'POST', requests_mock.ANY, status_code=500)

            query = self.model_query(cells=[cell])
            location = self.provider.locate(query)
            self.check_model_location(location, None)

        self.check_raven([('HTTPError', 1)])
        self.check_stats(
            counter=['m.fallback.lookup_status.500'],
            timer=['m.fallback.lookup'])

    def test_no_call_made_when_not_allowed_for_apikey(self):
        cells = CellFactory.build_batch(2)
        wifis = WifiFactory.build_batch(2)
        self.provider.api_key.allow_fallback = False

        query = self.model_query(cells=cells, wifis=wifis)
        self.check_should_locate(query, False)

    def test_should_not_provide_location_if_one_wifi_provided(self):
        wifi = WifiFactory.build()

        query = self.model_query(wifis=[wifi])
        self.check_should_locate(query, False)

    def test_should_not_provide_location_without_cell_or_wifi_data(self):
        query = self.model_query()
        self.check_should_locate(query, False)

    def test_should_not_provide_location_if_malformed_cell(self):
        malformed_cell = CellFactory.build()
        malformed_cell.mcc = 99999

        query = self.model_query(cells=[malformed_cell])
        self.check_should_locate(query, False)

    def test_should_not_provide_location_if_malformed_wifi(self):
        wifi = WifiFactory.build()
        malformed_wifi = WifiFactory.build()
        malformed_wifi.key = 'abcd'

        query = self.model_query(wifis=[wifi, malformed_wifi])
        self.check_should_locate(query, False)

    def test_should_provide_location_if_only_empty_location_found(self):
        wifis = WifiFactory.build_batch(2)

        query = self.model_query(wifis=wifis)
        self.check_should_locate(query, True)

    def test_should_provide_location_if_only_geoip_location_found(self):
        london = self.london_model
        wifis = WifiFactory.build_batch(2)
        geoip_pos = Position(
            source=DataSource.GeoIP,
            lat=london.lat,
            lon=london.lon,
            accuracy=london.range)

        query = self.model_query(wifis=wifis, geoip=london.ip)
        self.check_should_locate(query, True, location=geoip_pos)

    def test_should_not_provide_location_if_non_geoip_location_found(self):
        wifis = WifiFactory.build_batch(2)
        internal_pos = Position(
            source=DataSource.Internal, lat=1.0, lon=1.0, accuracy=1.0)

        query = self.model_query(wifis=wifis)
        self.check_should_locate(query, False, location=internal_pos)

    def test_rate_limiting_allows_calls_below_ratelimit(self):
        cell = CellFactory()

        with requests_mock.Mocker() as mock_request:
            mock_request.register_uri(
                'POST', requests_mock.ANY, json=self.fallback_location)

            for _ in range(self.provider.ratelimit):
                query = self.model_query(cells=[cell])
                location = self.provider.locate(query)
                self.check_model_location(location, self.fallback_model)

    def test_rate_limiting_blocks_calls_above_ratelimit(self):
        cell = CellFactory()

        with requests_mock.Mocker() as mock_request:
            mock_request.register_uri(
                'POST', requests_mock.ANY, json=self.fallback_location)

            ratelimit_key = self.provider.get_ratelimit_key()
            self.redis_client.set(ratelimit_key, self.provider.ratelimit)

            query = self.model_query(cells=[cell])
            location = self.provider.locate(query)
            self.check_model_location(location, None)

    def test_redis_failure_during_ratelimit_prevents_external_call(self):
        cell = CellFactory.build()
        mock_redis_client = self._mock_redis_client()
        mock_redis_client.pipeline.side_effect = RedisError()

        with requests_mock.Mocker() as mock_request:
            mock_request.register_uri(
                'POST', requests_mock.ANY, json=self.fallback_location)

            with mock.patch.object(self.provider, 'redis_client',
                                   mock_redis_client):
                query = self.model_query(cells=[cell])
                location = self.provider.locate(query)
                self.check_model_location(location, None)

            self.assertTrue(mock_redis_client.pipeline.called)
            self.assertFalse(mock_request.called)

    def test_redis_failure_during_get_cache_allows_external_call(self):
        cell = CellFactory.build()
        mock_redis_client = self._mock_redis_client()
        mock_redis_client.get.side_effect = RedisError()

        with requests_mock.Mocker() as mock_request:
            mock_request.register_uri(
                'POST', requests_mock.ANY, json=self.fallback_location)

            with mock.patch.object(self.provider, 'redis_client',
                                   mock_redis_client):
                query = self.model_query(cells=[cell])
                location = self.provider.locate(query)
                self.check_model_location(location, self.fallback_model)

            self.assertTrue(mock_redis_client.get.called)
            self.assertTrue(mock_request.called)

    def test_redis_failure_during_set_cache_returns_location(self):
        cell = CellFactory.build()
        mock_redis_client = self._mock_redis_client()
        mock_redis_client.get.return_value = None
        mock_redis_client.set.side_effect = RedisError()

        with requests_mock.Mocker() as mock_request:
            mock_request.register_uri(
                'POST', requests_mock.ANY, json=self.fallback_location)

            with mock.patch.object(self.provider, 'redis_client',
                                   mock_redis_client):
                query = self.model_query(cells=[cell])
                location = self.provider.locate(query)
                self.check_model_location(location, self.fallback_model)

            self.assertTrue(mock_redis_client.get.called)
            self.assertTrue(mock_redis_client.set.called)
            self.assertTrue(mock_request.called)

    def test_single_cell_results_cached_preventing_external_call(self):
        cell = CellFactory.build()

        with requests_mock.Mocker() as mock_request:
            mock_request.register_uri(
                'POST', requests_mock.ANY, json=self.fallback_location)

            query = self.model_query(cells=[cell])
            query['cell'][0]['signal'] = -77
            location = self.provider.locate(query)
            self.check_model_location(location, self.fallback_model)

            self.assertEqual(mock_request.call_count, 1)
            self.check_stats(
                counter=[
                    'm.fallback.lookup_status.200',
                    'm.fallback.cache.miss',
                ],
                timer=['m.fallback.lookup'])

            # vary the signal strength, not part of cache key
            query['cell'][0]['signal'] = -82
            location = self.provider.locate(query)
            self.check_model_location(location, self.fallback_model)

            self.assertEqual(mock_request.call_count, 1)
            self.check_stats(
                counter=[
                    'm.fallback.lookup_status.200',
                    'm.fallback.cache.hit',
                ],
                timer=['m.fallback.lookup'])

    def test_empty_result_from_fallback_cached(self):
        cell = CellFactory.build()

        with requests_mock.Mocker() as mock_request:
            mock_request.register_uri(
                'POST',
                requests_mock.ANY,
                json=LocationNotFound.json_body(),
                status_code=404
            )

            query = self.model_query(cells=[cell])
            location = self.provider.locate(query)
            self.check_model_location(location, None)

            self.assertEqual(mock_request.call_count, 1)
            self.check_stats(
                counter=[
                    'm.fallback.lookup_status.404',
                    'm.fallback.cache.miss',
                ],
                timer=['m.fallback.lookup'])

            query = self.model_query(cells=[cell])
            location = self.provider.locate(query)
            self.check_model_location(location, None)

            self.assertEqual(mock_request.call_count, 1)
            self.check_stats(
                counter=[
                    'm.fallback.lookup_status.404',
                    'm.fallback.cache.hit',
                ],
                timer=['m.fallback.lookup'])

    def test_dont_set_cache_value_retrieved_from_cache(self):
        cell = CellFactory.build()
        mock_redis_client = self._mock_redis_client()
        mock_redis_client.get.return_value = json.dumps(self.fallback_location)

        with requests_mock.Mocker() as mock_request:
            mock_request.register_uri(
                'POST', requests_mock.ANY, json=self.fallback_location)

            with mock.patch.object(self.provider, 'redis_client',
                                   mock_redis_client):
                query = self.model_query(cells=[cell])
                location = self.provider.locate(query)
                self.check_model_location(location, self.fallback_model)

            self.assertTrue(mock_redis_client.get.called)
            self.assertFalse(mock_redis_client.set.called)

    def test_cache_expire_set_to_0_disables_caching(self):
        cell = CellFactory.build()
        mock_redis_client = self._mock_redis_client()
        mock_redis_client.get.return_value = json.dumps(self.fallback_location)
        self.provider.cache_expire = 0

        with requests_mock.Mocker() as mock_request:
            mock_request.register_uri(
                'POST', requests_mock.ANY, json=self.fallback_location)

            with mock.patch.object(self.provider, 'redis_client',
                                   mock_redis_client):
                query = self.model_query(cells=[cell])
                location = self.provider.locate(query)
                self.check_model_location(location, self.fallback_model)

            self.assertFalse(mock_redis_client.get.called)
            self.assertFalse(mock_redis_client.set.called)

    def test_dont_cache_when_wifi_keys_present(self):
        cell = CellFactory.build()
        wifis = WifiFactory.build_batch(2)
        mock_redis_client = self._mock_redis_client()
        mock_redis_client.get.return_value = json.dumps(self.fallback_location)

        with requests_mock.Mocker() as mock_request:
            mock_request.register_uri(
                'POST', requests_mock.ANY, json=self.fallback_location)

            with mock.patch.object(self.provider, 'redis_client',
                                   mock_redis_client):

                query = self.model_query(cells=[cell], wifis=wifis)
                location = self.provider.locate(query)
                self.check_model_location(location, self.fallback_model)

            self.assertFalse(mock_redis_client.get.called)
            self.assertFalse(mock_redis_client.set.called)
