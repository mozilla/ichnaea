import colander
import mock
import requests_mock
from redis import RedisError
from requests.exceptions import RequestException

from ichnaea.api.exceptions import LocationNotFound
from ichnaea.api.locate.constants import DataSource
from ichnaea.api.locate.fallback import (
    DisabledCache,
    ExternalResult,
    FallbackCache,
    FallbackPositionSource,
    OUTBOUND_SCHEMA,
    RESULT_SCHEMA,
)
from ichnaea.api.locate.query import Query
from ichnaea.api.locate.result import Position
from ichnaea.api.locate.tests.base import (
    BaseSourceTest,
    DummyModel,
)
from ichnaea.api.locate.tests.test_query import QueryTest
from ichnaea import floatjson
from ichnaea.tests.base import TestCase
from ichnaea.tests.factories import (
    ApiKeyFactory,
    CellShardFactory,
    WifiShardFactory,
)


class TestExternalResult(TestCase):

    def test_not_found(self):
        result = ExternalResult(None, None, None, None)
        self.assertTrue(result.not_found())

    def test_not_found_accuracy(self):
        result = ExternalResult(1.0, 1.0, None, None)
        self.assertTrue(result.not_found())

    def test_found(self):
        result = ExternalResult(1.0, 1.0, 10, None)
        self.assertFalse(result.not_found())

    def test_found_fallback(self):
        result = ExternalResult(1.0, 1.0, 10, 'lacf')
        self.assertFalse(result.not_found())

    def test_score(self):
        result = ExternalResult(1.0, 1.0, 10, None)
        self.assertAlmostEqual(result.score, 10.0)

    def test_score_fallback(self):
        result = ExternalResult(1.0, 1.0, 10, 'lacf')
        self.assertAlmostEqual(result.score, 5.0)


class TestResultSchema(TestCase):

    schema = RESULT_SCHEMA

    def test_empty(self):
        with self.assertRaises(colander.Invalid):
            self.schema.deserialize({})

    def test_accuracy_float(self):
        data = self.schema.deserialize(
            {'location': {'lat': 1.0, 'lng': 1.0}, 'accuracy': 11.6})
        self.assertEqual(
            data, {'lat': 1.0, 'lon': 1.0, 'accuracy': 11.6, 'fallback': None})

    def test_accuracy_missing(self):
        with self.assertRaises(colander.Invalid):
            self.schema.deserialize(
                {'location': {'lat': 1.0, 'lng': 1.0}, 'fallback': 'lacf'})

    def test_fallback(self):
        data = self.schema.deserialize(
            {'location': {'lat': 1.0, 'lng': 1.0},
             'accuracy': 10.0, 'fallback': 'lacf'})
        self.assertEqual(
            data, {'lat': 1.0, 'lon': 1.0, 'accuracy': 10.0,
                   'fallback': 'lacf'})

    def test_fallback_invalid(self):
        data = self.schema.deserialize(
            {'location': {'lat': 1.0, 'lng': 1.0},
             'accuracy': 10.0, 'fallback': 'cidf'})
        self.assertEqual(
            data, {'lat': 1.0, 'lon': 1.0, 'accuracy': 10.0, 'fallback': None})

    def test_fallback_missing(self):
        data = self.schema.deserialize(
            {'location': {'lat': 1.0, 'lng': 1.0}, 'accuracy': 10.0})
        self.assertEqual(
            data, {'lat': 1.0, 'lon': 1.0, 'accuracy': 10.0, 'fallback': None})

    def test_location_incomplete(self):
        with self.assertRaises(colander.Invalid):
            self.schema.deserialize(
                {'location': {'lng': 1.0}, 'accuracy': 10.0,
                 'fallback': 'lacf'})

    def test_location_missing(self):
        with self.assertRaises(colander.Invalid):
            self.schema.deserialize({'accuracy': 10.0, 'fallback': 'lacf'})


class TestOutboundSchema(TestCase):

    schema = OUTBOUND_SCHEMA

    def test_empty(self):
        self.assertEqual(self.schema.deserialize({}), {})
        self.assertEqual(self.schema.deserialize({'unknown_field': 1}), {})

    def test_fallback(self):
        self.assertEqual(self.schema.deserialize(
            {'fallbacks': {'ipf': False}}),
            {'fallbacks': {}})
        self.assertEqual(self.schema.deserialize(
            {'fallbacks': {'lacf': False}}),
            {'fallbacks': {'lacf': False}})
        self.assertEqual(self.schema.deserialize(
            {'fallbacks': {'ipf': True, 'lacf': False}}),
            {'fallbacks': {'lacf': False}})

    def test_query(self):
        query = Query()
        data = self.schema.deserialize(query.internal_query())
        self.assertEqual(data, {'fallbacks': {'lacf': True}})

    def test_cell(self):
        cell = CellShardFactory.build()
        query = Query(cell=[
            {'radio': cell.radio, 'mcc': cell.mcc, 'mnc': cell.mnc,
             'lac': cell.lac, 'cid': cell.cid, 'signal': -70, 'ta': 15,
             'unknown_field': 'foo'}])
        data = self.schema.deserialize(query.internal_query())
        self.assertEqual(data, {
            'cellTowers': [{
                'radioType': cell.radio.name,
                'mobileCountryCode': cell.mcc,
                'mobileNetworkCode': cell.mnc,
                'locationAreaCode': cell.lac,
                'cellId': cell.cid,
                'signalStrength': -70,
                'timingAdvance': 15,
            }],
            'fallbacks': {'lacf': True},
        })

    def test_wifi(self):
        wifis = WifiShardFactory.build_batch(2)
        query = Query(wifi=[
            {'mac': wifi.mac, 'signal': -90, 'ssid': 'my'} for wifi in wifis])
        data = self.schema.deserialize(query.internal_query())
        self.assertEqual(data, {
            'wifiAccessPoints': [{
                'macAddress': wifis[0].mac,
                'signalStrength': -90,
                'ssid': 'my',
            }, {
                'macAddress': wifis[1].mac,
                'signalStrength': -90,
                'ssid': 'my',
            }],
            'fallbacks': {'lacf': True},
        })


class TestCache(QueryTest):

    def setUp(self):
        super(TestCache, self).setUp()
        self.cache = FallbackCache(
            self.raven_client, self.redis_client, self.stats_client,
            cache_expire=600)

    def test_disabled(self):
        cache = DisabledCache()
        query = Query()
        self.assertEqual(
            cache.set(query, ExternalResult(None, None, None, None)), None)
        self.assertEqual(cache.get(query), None)

    def test_get_cell(self):
        cells = CellShardFactory.build_batch(1)
        query = Query(cell=self.cell_model_query(cells))
        self.assertEqual(self.cache.get(query), None)
        self.check_stats(counter=[
            ('locate.fallback.cache', 1, 1, ['status:miss']),
        ])

    def test_set_cell(self):
        cell = CellShardFactory.build()
        query = Query(cell=self.cell_model_query([cell]))
        result = ExternalResult(cell.lat, cell.lon, cell.radius, None)
        self.cache.set(query, result)
        keys = self.redis_client.keys('cache:fallback:cell:*')
        self.assertEqual(len(keys), 1)
        self.assertTrue(500 < self.redis_client.ttl(keys[0]) <= 600)
        self.assertEqual(self.cache.get(query), result)
        self.check_stats(counter=[
            ('locate.fallback.cache', 1, 1, ['status:hit']),
        ])

    def test_set_cell_not_found(self):
        cell = CellShardFactory.build()
        query = Query(cell=self.cell_model_query([cell]))
        result = ExternalResult(None, None, None, None)
        self.cache.set(query, result)
        keys = self.redis_client.keys('cache:fallback:cell:*')
        self.assertEqual(len(keys), 1)
        self.assertEqual(self.redis_client.get(keys[0]), b'"404"')
        self.assertEqual(self.cache.get(query), result)
        self.check_stats(counter=[
            ('locate.fallback.cache', 1, 1, ['status:hit']),
        ])

    def test_get_cell_multi(self):
        cells = CellShardFactory.build_batch(2)
        query = Query(cell=self.cell_model_query(cells))
        self.assertEqual(self.cache.get(query), None)
        self.check_stats(counter=[
            ('locate.fallback.cache', 1, 1, ['status:bypassed']),
        ])

    def test_get_wifi(self):
        wifis = WifiShardFactory.build_batch(2)
        query = Query(wifi=self.wifi_model_query(wifis))
        self.assertEqual(self.cache.get(query), None)
        self.check_stats(counter=[
            ('locate.fallback.cache', 1, 1, ['status:miss']),
        ])

    def test_set_wifi(self):
        wifis = WifiShardFactory.build_batch(2)
        wifi = wifis[0]
        query = Query(wifi=self.wifi_model_query(wifis))
        result = ExternalResult(wifi.lat, wifi.lon, wifi.radius, None)
        self.cache.set(query, result)
        self.assertEqual(self.cache.get(query), result)
        self.check_stats(counter=[
            ('locate.fallback.cache', 1, 1, ['status:hit']),
        ])

    def test_set_wifi_inconsistent(self):
        wifis1 = WifiShardFactory.build_batch(2)
        self.cache.set(
            Query(wifi=self.wifi_model_query(wifis1)),
            ExternalResult(wifis1[0].lat, wifis1[0].lon, 100, None))

        # similar lat/lon, worse accuracy
        wifis2 = WifiShardFactory.build_batch(
            2, lat=wifis1[0].lat + 0.0001, lon=wifis1[0].lon)
        self.cache.set(
            Query(wifi=self.wifi_model_query(wifis2)),
            ExternalResult(wifis2[0].lat, wifis2[0].lon, 200, None))

        # check combined query, avg lat/lon, max accuracy
        query = Query(wifi=self.wifi_model_query(wifis1 + wifis2))
        self.assertEqual(
            self.cache.get(query),
            ((wifis1[0].lat + wifis2[0].lat) / 2, wifis1[0].lon, 200, None))

        # different lat/lon
        wifis3 = WifiShardFactory.build_batch(2, lat=wifis1[0].lat + 10.0)
        self.cache.set(
            Query(wifi=self.wifi_model_query(wifis3)),
            ExternalResult(wifis3[0].lat, wifis3[0].lon, 300, None))

        # check combined query, inconsistent result
        query = Query(wifi=self.wifi_model_query(wifis1 + wifis2 + wifis3))
        self.assertEqual(self.cache.get(query), None)

        self.check_stats(counter=[
            ('locate.fallback.cache', 1, 1, ['status:hit']),
            ('locate.fallback.cache', 1, 1, ['status:inconsistent']),
        ])

    def test_get_mixed(self):
        cells = CellShardFactory.build_batch(1)
        wifis = WifiShardFactory.build_batch(2)
        query = Query(
            cell=self.cell_model_query(cells),
            wifi=self.wifi_model_query(wifis))
        self.assertEqual(self.cache.get(query), None)
        self.check_stats(counter=[
            ('locate.fallback.cache', 1, 1, ['status:bypassed']),
        ])


class TestSource(BaseSourceTest):

    TestSource = FallbackPositionSource
    settings = {
        'url': 'https://localhost:9/?api',
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
            lat=51.5366, lon=0.03989, radius=1500.0)

        self.fallback_result = {
            'location': {
                'lat': self.fallback_model.lat,
                'lng': self.fallback_model.lon,
            },
            'accuracy': float(self.fallback_model.radius),
            'fallback': 'lacf',
        }
        self.fallback_cached_result = floatjson.float_dumps({
            'lat': self.fallback_model.lat,
            'lon': self.fallback_model.lon,
            'accuracy': float(self.fallback_model.radius),
            'fallback': 'lacf',
        })

    def _mock_redis_client(self):
        client = mock.Mock()
        client.pipeline.return_value = client
        client.__enter__ = mock.Mock(return_value=client)
        client.__exit__ = mock.Mock(return_value=None)
        client.expire.return_value = mock.Mock()
        client.get.return_value = mock.Mock()
        client.mget.return_value = mock.Mock()
        client.set.return_value = mock.Mock()
        client.mset.return_value = mock.Mock()
        return client

    def test_cache(self):
        source = self.TestSource(
            settings={'cache_expire': '60'},
            geoip_db=self.geoip_db,
            raven_client=self.raven_client,
            redis_client=self.redis_client,
            stats_client=self.stats_client,
        )
        self.assertTrue(isinstance(source.cache, FallbackCache))
        self.assertEqual(source.cache.cache_expire, 60)

    def test_no_cache(self):
        source = self.TestSource(
            settings={'cache_expire': '0'},
            geoip_db=self.geoip_db,
            raven_client=self.raven_client,
            redis_client=self.redis_client,
            stats_client=self.stats_client,
        )
        self.assertTrue(isinstance(source.cache, DisabledCache))

    def test_success(self):
        cell = CellShardFactory.build()

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
            results = self.source.search(query)
            self.check_model_results(results, [self.fallback_model])
            self.assertAlmostEqual(
                results.best(query.expected_accuracy).score, 5.0, 4)

            request_json = mock_request.request_history[0].json()

        self.assertEqual(request_json['fallbacks'], {'lacf': True})
        self.check_stats(counter=[
            ('locate.fallback.lookup', ['status:200']),
        ], timer=[
            'locate.fallback.lookup',
        ])

    def test_failed_call(self):
        cell = CellShardFactory.build()

        with requests_mock.Mocker() as mock_request:
            def raise_request_exception(request, context):
                raise RequestException()

            mock_request.register_uri(
                'POST', requests_mock.ANY, json=raise_request_exception)

            query = self.model_query(cells=[cell])
            results = self.source.search(query)
            self.check_model_results(results, None)

    def test_invalid_json(self):
        cell = CellShardFactory.build()

        with requests_mock.Mocker() as mock_request:
            mock_request.register_uri(
                'POST', requests_mock.ANY, json=['invalid json'])

            query = self.model_query(cells=[cell])
            results = self.source.search(query)
            self.check_model_results(results, None)

    def test_malformed_json(self):
        cell = CellShardFactory.build()

        with requests_mock.Mocker() as mock_request:
            mock_request.register_uri(
                'POST', requests_mock.ANY, content=b'[invalid json')

            query = self.model_query(cells=[cell])
            results = self.source.search(query)
            self.check_model_results(results, None)

    def test_403_response(self):
        cell = CellShardFactory.build()

        with requests_mock.Mocker() as mock_request:
            mock_request.register_uri(
                'POST', requests_mock.ANY, status_code=403)

            query = self.model_query(cells=[cell])
            results = self.source.search(query)
            self.check_model_results(results, None)

        self.check_raven([('HTTPError', 1)])
        self.check_stats(counter=[
            ('locate.fallback.lookup', ['status:403']),
        ])

    def test_404_response(self):
        cell = CellShardFactory.build()

        with requests_mock.Mocker() as mock_request:
            mock_request.register_uri(
                'POST', requests_mock.ANY,
                json=LocationNotFound.json_body(),
                status_code=404)

            query = self.model_query(cells=[cell])
            results = self.source.search(query)
            self.check_model_results(results, None)

        self.check_raven([('HTTPError', 0)])
        self.check_stats(counter=[
            ('locate.fallback.lookup', ['status:404']),
        ])

    def test_500_response(self):
        cell = CellShardFactory.build()

        with requests_mock.Mocker() as mock_request:
            mock_request.register_uri(
                'POST', requests_mock.ANY, status_code=500)

            query = self.model_query(cells=[cell])
            results = self.source.search(query)
            self.check_model_results(results, None)

        self.check_raven([('HTTPError', 1)])
        self.check_stats(counter=[
            ('locate.fallback.lookup', ['status:500']),
        ], timer=[
            'locate.fallback.lookup',
        ])

    def test_api_key_disallows(self):
        api_key = ApiKeyFactory.build(allow_fallback=False)
        cells = CellShardFactory.build_batch(2)
        wifis = WifiShardFactory.build_batch(2)

        query = self.model_query(cells=cells, wifis=wifis, api_key=api_key)
        self.check_should_search(query, False)

    def test_check_one_wifi(self):
        wifi = WifiShardFactory.build()

        query = self.model_query(wifis=[wifi])
        self.check_should_search(query, False)

    def test_check_empty(self):
        query = self.model_query()
        self.check_should_search(query, False)

    def test_check_invalid_cell(self):
        malformed_cell = CellShardFactory.build()
        malformed_cell.mcc = 99999

        query = self.model_query(cells=[malformed_cell])
        self.check_should_search(query, False)

    def test_check_invalid_wifi(self):
        wifi = WifiShardFactory.build()
        malformed_wifi = WifiShardFactory.build()
        malformed_wifi.mac = 'abcd'

        query = self.model_query(wifis=[wifi, malformed_wifi])
        self.check_should_search(query, False)

    def test_check_empty_result(self):
        wifis = WifiShardFactory.build_batch(2)

        query = self.model_query(wifis=wifis)
        self.check_should_search(query, True)

    def test_check_geoip_result(self):
        london = self.london_model
        wifis = WifiShardFactory.build_batch(2)
        results = Position(
            source=DataSource.geoip,
            lat=london.lat,
            lon=london.lon,
            accuracy=float(london.radius)).as_list()

        query = self.model_query(wifis=wifis, ip=london.ip)
        self.check_should_search(query, True, results=results)

    def test_check_already_good_result(self):
        wifis = WifiShardFactory.build_batch(2)
        results = Position(
            source=DataSource.internal,
            lat=1.0, lon=1.0, accuracy=1.0).as_list()

        query = self.model_query(wifis=wifis)
        self.check_should_search(query, False, results=results)

    def test_rate_limit_allow(self):
        cell = CellShardFactory()

        with requests_mock.Mocker() as mock_request:
            mock_request.register_uri(
                'POST', requests_mock.ANY, json=self.fallback_result)

            for _ in range(self.source.ratelimit):
                query = self.model_query(cells=[cell])
                results = self.source.search(query)
                self.check_model_results(results, [self.fallback_model])

    def test_rate_limit_blocks(self):
        cell = CellShardFactory()

        with requests_mock.Mocker() as mock_request:
            mock_request.register_uri(
                'POST', requests_mock.ANY, json=self.fallback_result)

            ratelimit_key = self.source._ratelimit_key()
            self.redis_client.set(ratelimit_key, self.source.ratelimit)

            query = self.model_query(cells=[cell])
            results = self.source.search(query)
            self.check_model_results(results, None)

    def test_rate_limit_redis_failure(self):
        cell = CellShardFactory.build()
        mock_redis_client = self._mock_redis_client()
        mock_redis_client.pipeline.side_effect = RedisError()

        with requests_mock.Mocker() as mock_request:
            mock_request.register_uri(
                'POST', requests_mock.ANY, json=self.fallback_result)

            with mock.patch.object(self.source, 'redis_client',
                                   mock_redis_client):
                query = self.model_query(cells=[cell])
                results = self.source.search(query)
                self.check_model_results(results, None)

            self.assertTrue(mock_redis_client.pipeline.called)
            self.assertFalse(mock_request.called)

    def test_get_cache_redis_failure(self):
        cell = CellShardFactory.build()
        mock_redis_client = self._mock_redis_client()
        mock_redis_client.mget.side_effect = RedisError()

        with requests_mock.Mocker() as mock_request:
            mock_request.register_uri(
                'POST', requests_mock.ANY, json=self.fallback_result)

            with mock.patch.object(self.source.cache, 'redis_client',
                                   mock_redis_client):
                query = self.model_query(cells=[cell])
                results = self.source.search(query)
                self.check_model_results(results, [self.fallback_model])

            self.assertTrue(mock_redis_client.mget.called)
            self.assertTrue(mock_request.called)

        self.check_stats(counter=[
            ('locate.fallback.cache', ['status:failure']),
        ])

    def test_set_cache_redis_failure(self):
        cell = CellShardFactory.build()
        mock_redis_client = self._mock_redis_client()
        mock_redis_client.mget.return_value = []
        mock_redis_client.mset.side_effect = RedisError()
        mock_redis_client.expire.side_effect = RedisError()
        mock_redis_client.execute.side_effect = RedisError()

        with requests_mock.Mocker() as mock_request:
            mock_request.register_uri(
                'POST', requests_mock.ANY, json=self.fallback_result)

            with mock.patch.object(self.source.cache, 'redis_client',
                                   mock_redis_client):
                query = self.model_query(cells=[cell])
                results = self.source.search(query)
                self.check_model_results(results, [self.fallback_model])

            self.assertTrue(mock_redis_client.mget.called)
            self.assertTrue(mock_redis_client.mset.called)
            self.assertTrue(mock_request.called)

        self.check_stats(counter=[
            ('locate.fallback.cache', ['status:miss']),
        ])

    def test_cache_single_cell(self):
        cell = CellShardFactory.build()

        with requests_mock.Mocker() as mock_request:
            mock_request.register_uri(
                'POST', requests_mock.ANY, json=self.fallback_result)

            query = self.model_query(cells=[cell])
            query.cell[0].signal = -77
            results = self.source.search(query)
            self.check_model_results(results, [self.fallback_model])
            self.assertAlmostEqual(
                results.best(query.expected_accuracy).score, 5.0, 4)

            self.assertEqual(mock_request.call_count, 1)
            self.check_stats(counter=[
                ('locate.fallback.cache', ['status:miss']),
                ('locate.fallback.lookup', ['status:200']),
            ], timer=[
                'locate.fallback.lookup',
            ])

            # vary the signal strength, not part of cache key
            query.cell[0].signal = -82
            results = self.source.search(query)
            self.check_model_results(results, [self.fallback_model])
            self.assertAlmostEqual(
                results.best(query.expected_accuracy).score, 5.0, 4)

            self.assertEqual(mock_request.call_count, 1)
            self.check_stats(counter=[
                ('locate.fallback.cache', ['status:hit']),
                ('locate.fallback.lookup', ['status:200']),
            ], timer=[
                'locate.fallback.lookup',
            ])

    def test_cache_empty_result(self):
        cell = CellShardFactory.build()

        with requests_mock.Mocker() as mock_request:
            mock_request.register_uri(
                'POST',
                requests_mock.ANY,
                json=LocationNotFound.json_body(),
                status_code=404
            )

            query = self.model_query(cells=[cell])
            results = self.source.search(query)
            self.check_model_results(results, None)

            self.assertEqual(mock_request.call_count, 1)
            self.check_stats(counter=[
                ('locate.fallback.cache', ['status:miss']),
                ('locate.fallback.lookup', ['status:404']),
            ])

            query = self.model_query(cells=[cell])
            results = self.source.search(query)
            self.check_model_results(results, None)

            self.assertEqual(mock_request.call_count, 1)
            self.check_stats(counter=[
                ('locate.fallback.cache', ['status:hit']),
                ('locate.fallback.lookup', ['status:404']),
            ])

    def test_dont_recache(self):
        cell = CellShardFactory.build()
        mock_redis_client = self._mock_redis_client()
        mock_redis_client.mget.return_value = [self.fallback_cached_result]

        with requests_mock.Mocker() as mock_request:
            mock_request.register_uri(
                'POST', requests_mock.ANY, json=self.fallback_result)

            with mock.patch.object(self.source.cache, 'redis_client',
                                   mock_redis_client):
                query = self.model_query(cells=[cell])
                results = self.source.search(query)
                self.check_model_results(results, [self.fallback_model])

            self.assertTrue(mock_redis_client.mget.called)
            self.assertFalse(mock_redis_client.mset.called)

        self.check_stats(counter=[
            ('locate.fallback.cache', ['status:hit']),
        ])
