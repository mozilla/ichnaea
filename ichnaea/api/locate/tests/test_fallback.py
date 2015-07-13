import mock
import requests_mock
import simplejson as json
from redis import RedisError
from requests.exceptions import RequestException

from ichnaea.api.exceptions import LocationNotFound
from ichnaea.api.locate.constants import DataSource
from ichnaea.api.locate.fallback import FallbackProvider
from ichnaea.api.locate.location import Position
from ichnaea.api.locate.tests.test_provider import (
    DummyModel,
    GeoIPProviderTest,
)
from ichnaea.tests.factories import (
    CellFactory,
    WifiFactory,
)


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
            query.cell[0]['signal'] = -77
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
            query.cell[0]['signal'] = -82
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
