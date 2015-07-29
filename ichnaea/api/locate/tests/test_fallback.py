import mock
import requests_mock
import simplejson as json
from redis import RedisError
from requests.exceptions import RequestException

from ichnaea.api.exceptions import LocationNotFound
from ichnaea.api.locate.constants import DataSource
from ichnaea.api.locate.fallback import FallbackPositionSource
from ichnaea.api.locate.result import Position
from ichnaea.api.locate.tests.base import (
    BaseSourceTest,
    DummyModel,
)
from ichnaea.tests.factories import (
    ApiKeyFactory,
    CellFactory,
    WifiFactory,
)


class TestSource(BaseSourceTest):

    TestSource = FallbackPositionSource
    settings = {
        'url': 'http://127.0.0.1:9/?api',
        'ratelimit': '3',
        'ratelimit_expire': '60',
        'ratelimit_interval': '2',
        'cache_expire': '60',
    }

    def setUp(self):
        super(TestSource, self).setUp()

        self.api_key = ApiKeyFactory.build(
            shortname='test', allow_fallback=True)
        self.fallback_model = DummyModel(
            lat=51.5366, lon=0.03989, accuracy=1500)

        self.fallback_result = {
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

    def test_success(self):
        cell = CellFactory.build()

        with requests_mock.Mocker() as mock_request:
            mock_request.register_uri(
                'POST', requests_mock.ANY, json=self.fallback_result)

            query = self.model_query(
                cells=[cell],
                fallback={
                    'lacf': True,
                    'ipf': False,
                },
            )
            result = self.source.search(query)
            self.check_model_result(result, self.fallback_model)

            request_json = mock_request.request_history[0].json()

        self.assertEqual(request_json['fallbacks'], {'lacf': True})
        self.check_stats(counter=[
            ('locate.fallback.lookup', ['status:200']),
        ], timer=[
            'locate.fallback.lookup',
        ])

    def test_failed_call(self):
        cell = CellFactory.build()

        with requests_mock.Mocker() as mock_request:
            def raise_request_exception(request, context):
                raise RequestException()

            mock_request.register_uri(
                'POST', requests_mock.ANY, json=raise_request_exception)

            query = self.model_query(cells=[cell])
            result = self.source.search(query)
            self.check_model_result(result, None)

    def test_invalid_json(self):
        cell = CellFactory.build()

        with requests_mock.Mocker() as mock_request:
            mock_request.register_uri(
                'POST', requests_mock.ANY, json=['invalid json'])

            query = self.model_query(cells=[cell])
            result = self.source.search(query)
            self.check_model_result(result, None)

    def test_malformed_json(self):
        cell = CellFactory.build()

        with requests_mock.Mocker() as mock_request:
            mock_request.register_uri(
                'POST', requests_mock.ANY, content=b'[invalid json')

            query = self.model_query(cells=[cell])
            result = self.source.search(query)
            self.check_model_result(result, None)

    def test_403_response(self):
        cell = CellFactory.build()

        with requests_mock.Mocker() as mock_request:
            mock_request.register_uri(
                'POST', requests_mock.ANY, status_code=403)

            query = self.model_query(cells=[cell])
            result = self.source.search(query)
            self.check_model_result(result, None)

        self.check_raven([('HTTPError', 1)])
        self.check_stats(counter=[
            ('locate.fallback.lookup', ['status:403']),
        ])

    def test_404_response(self):
        cell = CellFactory.build()

        with requests_mock.Mocker() as mock_request:
            mock_request.register_uri(
                'POST', requests_mock.ANY,
                json=LocationNotFound.json_body(),
                status_code=404)

            query = self.model_query(cells=[cell])
            result = self.source.search(query)
            self.check_model_result(result, None)

        self.check_raven([('HTTPError', 0)])
        self.check_stats(counter=[
            ('locate.fallback.lookup', ['status:404']),
        ])

    def test_500_response(self):
        cell = CellFactory.build()

        with requests_mock.Mocker() as mock_request:
            mock_request.register_uri(
                'POST', requests_mock.ANY, status_code=500)

            query = self.model_query(cells=[cell])
            result = self.source.search(query)
            self.check_model_result(result, None)

        self.check_raven([('HTTPError', 1)])
        self.check_stats(counter=[
            ('locate.fallback.lookup', ['status:500']),
        ], timer=[
            'locate.fallback.lookup',
        ])

    def test_api_key_disallows(self):
        api_key = ApiKeyFactory.build(allow_fallback=False)
        cells = CellFactory.build_batch(2)
        wifis = WifiFactory.build_batch(2)

        query = self.model_query(cells=cells, wifis=wifis, api_key=api_key)
        self.check_should_search(query, False)

    def test_check_one_wifi(self):
        wifi = WifiFactory.build()

        query = self.model_query(wifis=[wifi])
        self.check_should_search(query, False)

    def test_check_empty(self):
        query = self.model_query()
        self.check_should_search(query, False)

    def test_check_invalid_cell(self):
        malformed_cell = CellFactory.build()
        malformed_cell.mcc = 99999

        query = self.model_query(cells=[malformed_cell])
        self.check_should_search(query, False)

    def test_check_invalid_wifi(self):
        wifi = WifiFactory.build()
        malformed_wifi = WifiFactory.build()
        malformed_wifi.key = 'abcd'

        query = self.model_query(wifis=[wifi, malformed_wifi])
        self.check_should_search(query, False)

    def test_check_empty_result(self):
        wifis = WifiFactory.build_batch(2)

        query = self.model_query(wifis=wifis)
        self.check_should_search(query, True)

    def test_check_geoip_result(self):
        london = self.london_model
        wifis = WifiFactory.build_batch(2)
        geoip_pos = Position(
            source=DataSource.geoip,
            lat=london.lat,
            lon=london.lon,
            accuracy=london.range)

        query = self.model_query(wifis=wifis, ip=london.ip)
        self.check_should_search(query, True, result=geoip_pos)

    def test_check_already_good_result(self):
        wifis = WifiFactory.build_batch(2)
        internal_pos = Position(
            source=DataSource.internal, lat=1.0, lon=1.0, accuracy=1.0)

        query = self.model_query(wifis=wifis)
        self.check_should_search(query, False, result=internal_pos)

    def test_rate_limit_allow(self):
        cell = CellFactory()

        with requests_mock.Mocker() as mock_request:
            mock_request.register_uri(
                'POST', requests_mock.ANY, json=self.fallback_result)

            for _ in range(self.source.ratelimit):
                query = self.model_query(cells=[cell])
                result = self.source.search(query)
                self.check_model_result(result, self.fallback_model)

    def test_rate_limit_blocks(self):
        cell = CellFactory()

        with requests_mock.Mocker() as mock_request:
            mock_request.register_uri(
                'POST', requests_mock.ANY, json=self.fallback_result)

            ratelimit_key = self.source._get_ratelimit_key()
            self.redis_client.set(ratelimit_key, self.source.ratelimit)

            query = self.model_query(cells=[cell])
            result = self.source.search(query)
            self.check_model_result(result, None)

    def test_rate_limit_redis_failure(self):
        cell = CellFactory.build()
        mock_redis_client = self._mock_redis_client()
        mock_redis_client.pipeline.side_effect = RedisError()

        with requests_mock.Mocker() as mock_request:
            mock_request.register_uri(
                'POST', requests_mock.ANY, json=self.fallback_result)

            with mock.patch.object(self.source, 'redis_client',
                                   mock_redis_client):
                query = self.model_query(cells=[cell])
                result = self.source.search(query)
                self.check_model_result(result, None)

            self.assertTrue(mock_redis_client.pipeline.called)
            self.assertFalse(mock_request.called)

    def test_get_cache_redis_failure(self):
        cell = CellFactory.build()
        mock_redis_client = self._mock_redis_client()
        mock_redis_client.get.side_effect = RedisError()

        with requests_mock.Mocker() as mock_request:
            mock_request.register_uri(
                'POST', requests_mock.ANY, json=self.fallback_result)

            with mock.patch.object(self.source, 'redis_client',
                                   mock_redis_client):
                query = self.model_query(cells=[cell])
                result = self.source.search(query)
                self.check_model_result(result, self.fallback_model)

            self.assertTrue(mock_redis_client.get.called)
            self.assertTrue(mock_request.called)

    def test_set_cache_redis_failure(self):
        cell = CellFactory.build()
        mock_redis_client = self._mock_redis_client()
        mock_redis_client.get.return_value = None
        mock_redis_client.set.side_effect = RedisError()

        with requests_mock.Mocker() as mock_request:
            mock_request.register_uri(
                'POST', requests_mock.ANY, json=self.fallback_result)

            with mock.patch.object(self.source, 'redis_client',
                                   mock_redis_client):
                query = self.model_query(cells=[cell])
                result = self.source.search(query)
                self.check_model_result(result, self.fallback_model)

            self.assertTrue(mock_redis_client.get.called)
            self.assertTrue(mock_redis_client.set.called)
            self.assertTrue(mock_request.called)

    def test_cache_single_cell(self):
        cell = CellFactory.build()

        with requests_mock.Mocker() as mock_request:
            mock_request.register_uri(
                'POST', requests_mock.ANY, json=self.fallback_result)

            query = self.model_query(cells=[cell])
            query.cell[0].signal = -77
            result = self.source.search(query)
            self.check_model_result(result, self.fallback_model)

            self.assertEqual(mock_request.call_count, 1)
            self.check_stats(counter=[
                ('locate.fallback.cache', ['status:miss']),
                ('locate.fallback.lookup', ['status:200']),
            ], timer=[
                'locate.fallback.lookup',
            ])

            # vary the signal strength, not part of cache key
            query.cell[0].signal = -82
            result = self.source.search(query)
            self.check_model_result(result, self.fallback_model)

            self.assertEqual(mock_request.call_count, 1)
            self.check_stats(counter=[
                ('locate.fallback.cache', ['status:hit']),
                ('locate.fallback.lookup', ['status:200']),
            ], timer=[
                'locate.fallback.lookup',
            ])

    def test_cache_empty_result(self):
        cell = CellFactory.build()

        with requests_mock.Mocker() as mock_request:
            mock_request.register_uri(
                'POST',
                requests_mock.ANY,
                json=LocationNotFound.json_body(),
                status_code=404
            )

            query = self.model_query(cells=[cell])
            result = self.source.search(query)
            self.check_model_result(result, None)

            self.assertEqual(mock_request.call_count, 1)
            self.check_stats(counter=[
                ('locate.fallback.cache', ['status:miss']),
                ('locate.fallback.lookup', ['status:404']),
            ], timer=[
                'locate.fallback.lookup',
            ])

            query = self.model_query(cells=[cell])
            result = self.source.search(query)
            self.check_model_result(result, None)

            self.assertEqual(mock_request.call_count, 1)
            self.check_stats(counter=[
                ('locate.fallback.cache', ['status:hit']),
                ('locate.fallback.lookup', ['status:404']),
            ], timer=[
                'locate.fallback.lookup',
            ])

    def test_dont_recache(self):
        cell = CellFactory.build()
        mock_redis_client = self._mock_redis_client()
        mock_redis_client.get.return_value = json.dumps(self.fallback_result)

        with requests_mock.Mocker() as mock_request:
            mock_request.register_uri(
                'POST', requests_mock.ANY, json=self.fallback_result)

            with mock.patch.object(self.source, 'redis_client',
                                   mock_redis_client):
                query = self.model_query(cells=[cell])
                result = self.source.search(query)
                self.check_model_result(result, self.fallback_model)

            self.assertTrue(mock_redis_client.get.called)
            self.assertFalse(mock_redis_client.set.called)

    def test_cache_expire_0(self):
        cell = CellFactory.build()
        mock_redis_client = self._mock_redis_client()
        mock_redis_client.get.return_value = json.dumps(self.fallback_result)
        self.source.cache_expire = 0

        with requests_mock.Mocker() as mock_request:
            mock_request.register_uri(
                'POST', requests_mock.ANY, json=self.fallback_result)

            with mock.patch.object(self.source, 'redis_client',
                                   mock_redis_client):
                query = self.model_query(cells=[cell])
                result = self.source.search(query)
                self.check_model_result(result, self.fallback_model)

            self.assertFalse(mock_redis_client.get.called)
            self.assertFalse(mock_redis_client.set.called)

    def test_cache_no_wifi(self):
        cell = CellFactory.build()
        wifis = WifiFactory.build_batch(2)
        mock_redis_client = self._mock_redis_client()
        mock_redis_client.get.return_value = json.dumps(self.fallback_result)

        with requests_mock.Mocker() as mock_request:
            mock_request.register_uri(
                'POST', requests_mock.ANY, json=self.fallback_result)

            with mock.patch.object(self.source, 'redis_client',
                                   mock_redis_client):

                query = self.model_query(cells=[cell], wifis=wifis)
                result = self.source.search(query)
                self.check_model_result(result, self.fallback_model)

            self.assertFalse(mock_redis_client.get.called)
            self.assertFalse(mock_redis_client.set.called)

        self.check_stats(counter=[
            ('locate.fallback.cache', ['status:bypassed']),
            ('locate.fallback.lookup', ['status:200']),
        ], timer=[
            'locate.fallback.lookup',
        ])
