import operator

import requests_mock
import simplejson as json
from sqlalchemy import text

from ichnaea.api.exceptions import (
    DailyLimitExceeded,
    InvalidAPIKey,
    LocationNotFound,
    ParseError,
)
from ichnaea.api.locate.constants import (
    BLUE_MIN_ACCURACY,
    BLUE_MAX_ACCURACY,
    CELL_MIN_ACCURACY,
    CELL_MAX_ACCURACY,
    CELLAREA_MIN_ACCURACY,
    CELLAREA_MAX_ACCURACY,
    WIFI_MIN_ACCURACY,
    WIFI_MAX_ACCURACY,
)
from ichnaea.api.locate.query import Query
from ichnaea.api.locate.result import (
    Position,
    Region,
)
from ichnaea.models import (
    ApiKey,
    BlueShard,
    CellArea,
    CellAreaOCID,
    CellOCID,
    CellShard,
    WifiShard,
    Radio,
)
from ichnaea.tests.base import ConnectionTestCase
from ichnaea.tests.factories import (
    ApiKeyFactory,
    BlueShardFactory,
    CellAreaFactory,
    CellShardFactory,
    WifiShardFactory,
)
from ichnaea import util

_sentinel = object()


class DummyModel(object):

    def __init__(self, lat=None, lon=None, radius=None,
                 code=None, name=None, ip=None):
        self.lat = lat
        self.lon = lon
        self.radius = radius
        self.code = code
        self.name = name
        self.ip = ip


def bound_model_accuracy(model, accuracy):
    if isinstance(model, BlueShard):
        accuracy = min(max(accuracy, BLUE_MIN_ACCURACY),
                       BLUE_MAX_ACCURACY)
    elif isinstance(model, (CellOCID, CellShard)):
        accuracy = min(max(accuracy, CELL_MIN_ACCURACY),
                       CELL_MAX_ACCURACY)
    elif isinstance(model, (CellArea, CellAreaOCID)):
        accuracy = min(max(accuracy, CELLAREA_MIN_ACCURACY),
                       CELLAREA_MAX_ACCURACY)
    elif isinstance(model, WifiShard):
        accuracy = min(max(accuracy, WIFI_MIN_ACCURACY),
                       WIFI_MAX_ACCURACY)
    return accuracy


class BaseSourceTest(ConnectionTestCase):

    api_type = 'locate'
    TestSource = None

    @classmethod
    def setUpClass(cls):
        super(BaseSourceTest, cls).setUpClass()
        cls.api_key = ApiKeyFactory.build(valid_key='test')
        bhutan = cls.geoip_data['Bhutan']
        cls.bhutan_model = DummyModel(
            lat=bhutan['latitude'],
            lon=bhutan['longitude'],
            radius=bhutan['radius'],
            code=bhutan['region_code'],
            name=bhutan['region_name'],
            ip=bhutan['ip'])
        london = cls.geoip_data['London']
        cls.london_model = DummyModel(
            lat=london['latitude'],
            lon=london['longitude'],
            radius=london['radius'],
            code=london['region_code'],
            name=london['region_name'],
            ip=london['ip'])

    def setUp(self):
        super(BaseSourceTest, self).setUp()
        self.source = self.TestSource(
            geoip_db=self.geoip_db,
            raven_client=self.raven_client,
            redis_client=self.redis_client,
            stats_client=self.stats_client,
        )

    def make_query(self, **kw):
        api_key = kw.pop('api_key', self.api_key)
        return Query(
            api_key=api_key,
            api_type=self.api_type,
            session=self.session,
            http_session=self.http_session,
            geoip_db=self.geoip_db,
            stats_client=self.stats_client,
            **kw)

    def model_query(self, blues=(), cells=(), wifis=(), **kw):
        query_blue = []
        if blues:
            for blue in blues:
                query_blue.append({'mac': blue.mac})

        query_cell = []
        if cells:
            for cell in cells:
                cell_query = {
                    'radio': cell.radio,
                    'mcc': cell.mcc,
                    'mnc': cell.mnc,
                    'lac': cell.lac,
                }
                if getattr(cell, 'cid', None) is not None:
                    cell_query['cid'] = cell.cid
                query_cell.append(cell_query)

        query_wifi = []
        if wifis:
            for wifi in wifis:
                query_wifi.append({'mac': wifi.mac})

        return self.make_query(
            blue=query_blue,
            cell=query_cell,
            wifi=query_wifi,
            **kw)

    def check_should_search(self, query, should, results=None):
        if results is None:
            results = self.source.result_list()
        self.assertIs(self.source.should_search(query, results), should)

    def check_model_results(self, results, models, **kw):
        type_ = self.TestSource.result_type

        if not models:
            self.assertEqual(len(results), 0)
            return

        expected = []
        if type_ is Position:
            check_func = self.assertAlmostEqual
            for model in models:
                expected.append({
                    'lat': kw.get('lat', model.lat),
                    'lon': kw.get('lon', model.lon),
                    'accuracy': bound_model_accuracy(
                        model, kw.get('accuracy', model.radius)),
                })

            # don't test ordering of results
            expected = sorted(expected, key=operator.itemgetter('lat', 'lon'))
            results = sorted(results, key=operator.attrgetter('lat', 'lon'))

        elif type_ is Region:
            check_func = self.assertEqual
            for model in models:
                expected.append({
                    'region_code': model.code,
                    'region_name': model.name,
                })
            # don't test ordering of results
            expected = sorted(expected, key=operator.itemgetter('region_code'))
            results = sorted(results, key=operator.attrgetter('region_code'))

        for expect, result in zip(expected, results):
            self.assertEqual(type(result), type_)
            for key, value in expect.items():
                check_func(getattr(result, key), value)


class BaseLocateTest(object):

    url = None
    apikey_metrics = True
    default_apikey = 'test'
    metric_path = None
    metric_type = None
    not_found = LocationNotFound

    @property
    def test_ip(self):
        # accesses data defined in GeoIPTestCase
        return self.geoip_data['London']['ip']

    @property
    def ip_response(self):  # pragma: no cover
        return {}

    def _call(self, body=None, api_key=_sentinel, ip=None, status=200,
              headers=None, method='post_json', **kw):
        if body is None:
            body = {}
        url = self.url
        if api_key:
            if api_key is _sentinel:
                api_key = self.default_apikey
            url += '?key=%s' % api_key
        extra_environ = {}
        if ip is not None:
            extra_environ = {'HTTP_X_FORWARDED_FOR': ip}
        call = getattr(self.app, method)
        if method in ('get', 'delete', 'head', 'options'):
            return call(url,
                        extra_environ=extra_environ,
                        status=status,
                        headers=headers,
                        **kw)
        else:
            return call(url, body,
                        content_type='application/json',
                        extra_environ=extra_environ,
                        status=status,
                        headers=headers,
                        **kw)

    def check_response(self, response, status):
        self.assertEqual(response.content_type, 'application/json')
        self.assertEqual(response.charset, 'UTF-8')
        self.assertEqual(response.headers['Access-Control-Allow-Origin'], '*')
        self.assertEqual(response.headers['Access-Control-Max-Age'], '2592000')
        if status == 'ok':
            self.assertEqual(response.json, self.ip_response)
        elif status == 'invalid_key':
            self.assertEqual(response.json, InvalidAPIKey.json_body())
        elif status == 'not_found':
            self.assertEqual(response.json, self.not_found.json_body())
        elif status == 'parse_error':
            self.assertEqual(response.json, ParseError.json_body())
        elif status == 'limit_exceeded':
            self.assertEqual(response.json, DailyLimitExceeded.json_body())

    def check_model_response(self, response, model,
                             region=None, fallback=None,
                             expected_names=(), **kw):
        expected = {'region': region}
        for name in ('lat', 'lon', 'accuracy'):
            if name in kw:
                expected[name] = kw[name]
            else:
                model_name = name
                if name == 'accuracy':
                    expected[name] = bound_model_accuracy(
                        model, getattr(model, 'radius'))
                else:
                    expected[name] = getattr(model, model_name)

        if fallback is not None:
            expected_names = set(expected_names).union(set(['fallback']))

        self.assertEqual(response.content_type, 'application/json')
        self.assertEqual(set(response.json.keys()), expected_names)

        return expected

    def model_query(self, blues=(), cells=(), wifis=()):
        query = {}
        if blues:
            query['bluetoothBeacons'] = []
            for blue in blues:
                query['bluetoothBeacons'].append({
                    'macAddress': blue.mac,
                })
        if cells:
            query['cellTowers'] = []
            for cell in cells:
                radio_name = cell.radio.name
                if radio_name == 'umts':
                    radio_name = 'wcdma'
                cell_query = {
                    'radioType': radio_name,
                    'mobileCountryCode': cell.mcc,
                    'mobileNetworkCode': cell.mnc,
                    'locationAreaCode': cell.lac,
                }
                if getattr(cell, 'cid', None) is not None:
                    cell_query['cellId'] = cell.cid
                if getattr(cell, 'psc', None) is not None:
                    cell_query['psc'] = cell.cid
                query['cellTowers'].append(cell_query)
        if wifis:
            query['wifiAccessPoints'] = []
            for wifi in wifis:
                query['wifiAccessPoints'].append({
                    'macAddress': wifi.mac,
                })
        return query


class CommonLocateTest(BaseLocateTest):
    # tests for all locate API's incl. region

    def test_get(self):
        res = self._call(ip=self.test_ip, method='get', status=200)
        self.check_response(res, 'ok')
        self.check_stats(counter=[
            ('request', [self.metric_path, 'method:get', 'status:200']),
        ], timer=[
            ('request', [self.metric_path, 'method:get']),
        ])

    def test_options(self):
        res = self._call(method='options', status=200)
        self.assertEqual(res.headers['Access-Control-Allow-Origin'], '*')
        self.assertEqual(res.headers['Access-Control-Max-Age'], '2592000')

    def test_unsupported_methods(self):
        self._call(method='delete', status=405)
        self._call(method='patch', status=405)
        self._call(method='put', status=405)

    def test_empty_body(self):
        res = self._call('', ip=self.test_ip, method='post', status=200)
        self.check_response(res, 'ok')
        if self.apikey_metrics:
            # ensure that a apiuser hyperloglog entry was added for today
            today = util.utcnow().date().strftime('%Y-%m-%d')
            expected = 'apiuser:%s:test:%s' % (self.metric_type, today)
            self.assertEqual(
                [key.decode('ascii') for key in self.redis_client.keys(
                    'apiuser:*')], [expected])
            # check that the ttl was set
            ttl = self.redis_client.ttl(expected)
            self.assertTrue(7 * 24 * 3600 < ttl <= 8 * 24 * 3600)

    def test_empty_json(self):
        res = self._call(ip=self.test_ip, status=200)
        self.check_response(res, 'ok')
        self.check_stats(counter=[
            ('request', [self.metric_path, 'method:post', 'status:200']),
        ], timer=[
            ('request', [self.metric_path, 'method:post']),
        ])
        if self.apikey_metrics:
            self.check_stats(counter=[
                (self.metric_type + '.query',
                    ['key:test', 'region:GB',
                     'blue:none', 'cell:none', 'wifi:none']),
                (self.metric_type + '.result',
                    ['key:test', 'region:GB', 'fallback_allowed:false',
                     'accuracy:low', 'status:hit', 'source:geoip']),
                (self.metric_type + '.source',
                    ['key:test', 'region:GB', 'source:geoip',
                     'accuracy:low', 'status:hit']),
            ])

    def test_error_no_json(self):
        res = self._call('\xae', method='post', status=400)
        self.check_response(res, 'parse_error')
        self.check_stats(counter=[
            (self.metric_type + '.request',
                [self.metric_path, 'key:test']),
        ])

    def test_error_no_mapping(self):
        res = self._call([1], status=400)
        self.check_response(res, 'parse_error')

    def test_error_invalid_key(self):
        res = self._call({'foo': 0}, ip=self.test_ip, status=200)
        self.check_response(res, 'ok')

    def test_no_api_key(self, status=400, response='invalid_key'):
        res = self._call(api_key=None, ip=self.test_ip, status=status)
        self.check_response(res, response)
        self.check_stats(counter=[
            (self.metric_type + '.request',
                [self.metric_path, 'key:none']),
        ])
        self.assertEqual(self.redis_client.keys('apiuser:*'), [])

    def test_invalid_api_key(self, status=400, response='invalid_key'):
        res = self._call(api_key='invalid_key', ip=self.test_ip, status=status)
        self.check_response(res, response)
        self.check_stats(counter=[
            (self.metric_type + '.request',
                [self.metric_path, 'key:none']),
        ])
        self.assertEqual(self.redis_client.keys('apiuser:*'), [])

    def test_unknown_api_key(self, status=400,
                             response='invalid_key', metric_key='invalid'):
        res = self._call(api_key='abcdefg', ip=self.test_ip, status=status)
        self.check_response(res, response)
        self.check_stats(counter=[
            (self.metric_type + '.request',
                [self.metric_path, 'key:' + metric_key]),
        ])
        self.assertEqual(self.redis_client.keys('apiuser:*'), [])

    def test_gzip(self):
        wifis = WifiShardFactory.build_batch(2)
        query = self.model_query(wifis=wifis)

        body = util.encode_gzip(json.dumps(query))
        headers = {
            'Content-Encoding': 'gzip',
        }
        res = self._call(body=body, headers=headers,
                         method='post', status=self.not_found.code)
        self.check_response(res, 'not_found')


class CommonPositionTest(BaseLocateTest):
    # tests for only the locate_v1 and locate_v2 API's

    def test_api_key_limit(self):
        api_key = ApiKeyFactory(maxreq=5)
        self.session.flush()

        # exhaust today's limit
        dstamp = util.utcnow().strftime('%Y%m%d')
        path = self.metric_path.split(':')[-1]
        key = 'apilimit:%s:%s:%s' % (api_key.valid_key, path, dstamp)
        self.redis_client.incr(key, 10)

        res = self._call(
            api_key=api_key.valid_key, ip=self.test_ip, status=403)
        self.check_response(res, 'limit_exceeded')

    def test_api_key_blocked(self):
        api_key = ApiKeyFactory(allow_locate=False)

        res = self._call(
            api_key=api_key.valid_key, ip=self.test_ip, status=400)
        self.check_response(res, 'invalid_key')

    def test_blue_not_found(self):
        blues = BlueShardFactory.build_batch(2)

        query = self.model_query(blues=blues)

        res = self._call(body=query, status=self.not_found.code)
        self.check_response(res, 'not_found')
        self.check_stats(counter=[
            ('request', [self.metric_path, 'method:post',
                         'status:%s' % self.not_found.code]),
            (self.metric_type + '.request', [self.metric_path, 'key:test']),
            (self.metric_type + '.query',
                ['key:test', 'region:none',
                 'geoip:false', 'blue:many', 'cell:none', 'wifi:none']),
            (self.metric_type + '.result', 'fallback_allowed:false',
                ['key:test', 'region:none', 'accuracy:high', 'status:miss']),
            (self.metric_type + '.source',
                ['key:test', 'region:none', 'source:internal',
                 'accuracy:high', 'status:miss']),
        ], timer=[
            ('request', [self.metric_path, 'method:post']),
        ])

    def test_cell_not_found(self):
        cell = CellShardFactory.build()

        query = self.model_query(cells=[cell])
        res = self._call(body=query, status=self.not_found.code)
        self.check_response(res, 'not_found')
        self.check_stats(counter=[
            ('request', [self.metric_path, 'method:post',
                         'status:%s' % self.not_found.code]),
            (self.metric_type + '.request', [self.metric_path, 'key:test']),
            (self.metric_type + '.query',
                ['key:test', 'region:none',
                 'geoip:false', 'blue:none', 'cell:one', 'wifi:none']),
            (self.metric_type + '.result',
                ['key:test', 'region:none', 'fallback_allowed:false',
                 'accuracy:medium', 'status:miss']),
            (self.metric_type + '.source',
                ['key:test', 'region:none', 'source:internal',
                 'accuracy:medium', 'status:miss']),
        ], timer=[
            ('request', [self.metric_path, 'method:post']),
        ])

    def test_cell_invalid_lac(self):
        cell = CellShardFactory.build(radio=Radio.wcdma, lac=0, cid=1)
        query = self.model_query(cells=[cell])
        res = self._call(body=query, status=self.not_found.code)
        self.check_response(res, 'not_found')

    def test_cell_lte_radio(self):
        cell = CellShardFactory(radio=Radio.lte)
        self.session.flush()

        query = self.model_query(cells=[cell])

        res = self._call(body=query)
        self.check_model_response(res, cell)
        self.check_stats(counter=[
            (self.metric_type + '.request', [self.metric_path, 'key:test']),
            ('request', [self.metric_path, 'method:post', 'status:200']),
        ])

    def test_cellarea(self):
        cell = CellAreaFactory()
        self.session.flush()

        query = self.model_query(cells=[cell])
        res = self._call(body=query)
        self.check_model_response(res, cell, fallback='lacf')
        self.check_stats(counter=[
            ('request', [self.metric_path, 'method:post', 'status:200']),
            (self.metric_type + '.request', [self.metric_path, 'key:test']),
            (self.metric_type + '.query',
                ['key:test', 'region:none',
                 'geoip:false', 'blue:none', 'cell:none', 'wifi:none']),
            (self.metric_type + '.result',
                ['key:test', 'region:none', 'fallback_allowed:false',
                 'accuracy:low', 'status:hit', 'source:internal']),
            (self.metric_type + '.source',
                ['key:test', 'region:none', 'source:internal',
                 'accuracy:low', 'status:hit']),
        ])

    def test_cellarea_with_lacf(self):
        cell = CellAreaFactory()
        self.session.flush()

        query = self.model_query(cells=[cell])
        query['fallbacks'] = {'lacf': True}

        res = self._call(body=query)
        self.check_model_response(res, cell, fallback='lacf')
        self.check_stats(counter=[
            ('request', [self.metric_path, 'method:post', 'status:200']),
            (self.metric_type + '.request', [self.metric_path, 'key:test']),
            (self.metric_type + '.query',
                ['key:test', 'region:none',
                 'geoip:false', 'blue:none', 'cell:none', 'wifi:none']),
            (self.metric_type + '.result',
                ['key:test', 'region:none', 'fallback_allowed:false',
                 'accuracy:low', 'status:hit', 'source:internal']),
            (self.metric_type + '.source',
                ['key:test', 'region:none', 'source:internal',
                 'accuracy:low', 'status:hit']),
        ])

    def test_cellarea_without_lacf(self):
        cell = CellAreaFactory()
        self.session.flush()

        query = self.model_query(cells=[cell])
        query['fallbacks'] = {'lacf': False}

        res = self._call(body=query, status=self.not_found.code)
        self.check_response(res, 'not_found')
        self.check_stats(counter=[
            ('request', [self.metric_path, 'method:post',
                         'status:%s' % self.not_found.code]),
            (self.metric_type + '.request', [self.metric_path, 'key:test']),
        ])

    def test_cellarea_with_different_fallback(self):
        cell = CellAreaFactory()
        self.session.flush()

        query = self.model_query(cells=[cell])
        query['fallbacks'] = {'ipf': True}

        res = self._call(body=query)
        self.check_model_response(res, cell, fallback='lacf')
        self.check_stats(counter=[
            ('request', [self.metric_path, 'method:post', 'status:200']),
            (self.metric_type + '.request', [self.metric_path, 'key:test']),
            (self.metric_type + '.result',
                ['key:test', 'region:none', 'fallback_allowed:false',
                 'accuracy:low', 'status:hit', 'source:internal']),
        ])

    def test_wifi_not_found(self):
        wifis = WifiShardFactory.build_batch(2)

        query = self.model_query(wifis=wifis)

        res = self._call(body=query, status=self.not_found.code)
        self.check_response(res, 'not_found')
        self.check_stats(counter=[
            ('request', [self.metric_path, 'method:post',
                         'status:%s' % self.not_found.code]),
            (self.metric_type + '.request', [self.metric_path, 'key:test']),
            (self.metric_type + '.query',
                ['key:test', 'region:none',
                 'geoip:false', 'blue:none', 'cell:none', 'wifi:many']),
            (self.metric_type + '.result', 'fallback_allowed:false',
                ['key:test', 'region:none', 'accuracy:high', 'status:miss']),
            (self.metric_type + '.source',
                ['key:test', 'region:none', 'source:internal',
                 'accuracy:high', 'status:miss']),
        ], timer=[
            ('request', [self.metric_path, 'method:post']),
        ])

    def test_ip_fallback_disabled(self):
        res = self._call(body={
            'fallbacks': {
                'ipf': 0,
            }},
            ip=self.test_ip,
            status=self.not_found.code)
        self.check_response(res, 'not_found')
        self.check_stats(counter=[
            ('request', [self.metric_path, 'method:post',
                         'status:%s' % self.not_found.code]),
            (self.metric_type + '.request', [self.metric_path, 'key:test']),
        ], timer=[
            ('request', [self.metric_path, 'method:post']),
        ])

    def test_fallback(self):
        # this tests a cell + wifi based query which gets a cell based
        # internal result and continues on to the fallback to get a
        # better wifi based result
        cells = CellShardFactory.create_batch(2, radio=Radio.wcdma)
        wifis = WifiShardFactory.build_batch(3)
        api_key = ApiKey.get(self.session, 'test')
        api_key.allow_fallback = True
        self.session.flush()

        with requests_mock.Mocker() as mock:
            response_result = {
                'location': {
                    'lat': 1.0,
                    'lng': 1.0,
                },
                'accuracy': 100,
            }
            mock.register_uri(
                'POST', requests_mock.ANY, json=response_result)

            query = self.model_query(cells=cells, wifis=wifis)
            res = self._call(body=query)

            send_json = mock.request_history[0].json()
            self.assertEqual(len(send_json['cellTowers']), 2)
            self.assertEqual(len(send_json['wifiAccessPoints']), 3)
            self.assertEqual(send_json['cellTowers'][0]['radioType'], 'wcdma')

        self.check_model_response(res, None, lat=1.0, lon=1.0, accuracy=100)
        self.check_stats(counter=[
            ('request', [self.metric_path, 'method:post', 'status:200']),
            (self.metric_type + '.request', [self.metric_path, 'key:test']),
            (self.metric_type + '.query',
                ['key:test', 'region:none',
                 'geoip:false', 'blue:none', 'cell:many', 'wifi:many']),
            (self.metric_type + '.result',
                ['key:test', 'region:none', 'fallback_allowed:true',
                 'accuracy:high', 'status:hit', 'source:fallback']),
            (self.metric_type + '.source',
                ['key:test', 'region:none', 'source:internal',
                 'accuracy:high', 'status:miss']),
            (self.metric_type + '.source',
                ['key:test', 'region:none', 'source:fallback',
                 'accuracy:high', 'status:hit']),
        ], timer=[
            ('request', [self.metric_path, 'method:post']),
        ])

    def test_fallback_used_with_geoip(self):
        cells = CellShardFactory.create_batch(2, radio=Radio.wcdma)
        wifis = WifiShardFactory.build_batch(3)
        api_key = ApiKey.get(self.session, 'test')
        api_key.allow_fallback = True
        self.session.flush()

        with requests_mock.Mocker() as mock:
            response_result = {
                'location': {
                    'lat': 1.0,
                    'lng': 1.0,
                },
                'accuracy': 100.0,
            }
            mock.register_uri(
                'POST', requests_mock.ANY, json=response_result)

            query = self.model_query(cells=cells, wifis=wifis)
            res = self._call(body=query, ip=self.test_ip)

            send_json = mock.request_history[0].json()
            self.assertEqual(len(send_json['cellTowers']), 2)
            self.assertEqual(len(send_json['wifiAccessPoints']), 3)

        self.check_model_response(res, None, lat=1.0, lon=1.0, accuracy=100)
        self.check_stats(counter=[
            ('request', [self.metric_path, 'method:post', 'status:200']),
            (self.metric_type + '.request', [self.metric_path, 'key:test']),
            (self.metric_type + '.result',
                ['key:test', 'region:GB', 'fallback_allowed:true',
                 'accuracy:high', 'status:hit', 'source:fallback']),
            (self.metric_type + '.source',
                ['key:test', 'region:GB', 'source:fallback',
                 'accuracy:high', 'status:hit']),
        ], timer=[
            ('request', [self.metric_path, 'method:post']),
        ])

    def test_floatjson(self):
        cell = CellShardFactory(lat=51.5, lon=(3.3 / 3 + 0.0001))
        self.session.flush()

        query = self.model_query(cells=[cell])
        res = self._call(body=query)
        self.check_model_response(res, cell)
        middle = '1.1001,' in res.text
        end = '1.1001}' in res.text
        self.assertTrue(middle or end, res.text)


class CommonLocateErrorTest(BaseLocateTest):
    # this is a standalone class to ensure DB isolation for dropping tables

    def tearDown(self):
        self.setup_tables(self.db_rw.engine)
        super(CommonLocateErrorTest, self).tearDown()

    def test_apikey_error(self, db_errors=0):
        cells = CellShardFactory.build_batch(2)
        wifis = WifiShardFactory.build_batch(2)

        self.session.execute(text('drop table %s;' % ApiKey.__tablename__))

        query = self.model_query(cells=cells, wifis=wifis)
        res = self._call(body=query, ip=self.test_ip)
        self.check_response(res, 'ok')
        self.check_raven([('ProgrammingError', db_errors)])

    def test_database_error(self, db_errors=0):
        cells = [
            CellShardFactory.build(radio=Radio.gsm),
            CellShardFactory.build(radio=Radio.wcdma),
            CellShardFactory.build(radio=Radio.lte),
        ]
        wifis = WifiShardFactory.build_batch(2)

        for model in (CellArea, CellOCID, CellAreaOCID):
            self.session.execute(text('drop table %s;' % model.__tablename__))
        for name in set([cell.__tablename__ for cell in cells]):
            self.session.execute(text('drop table %s;' % name))
        for name in set([wifi.__tablename__ for wifi in wifis]):
            self.session.execute(text('drop table %s;' % name))

        query = self.model_query(cells=cells, wifis=wifis)
        res = self._call(body=query, ip=self.test_ip)
        self.check_response(res, 'ok')
        self.check_stats(counter=[
            ('request', [self.metric_path, 'method:post', 'status:200']),
        ], timer=[
            ('request', [self.metric_path, 'method:post']),
        ])
        if self.apikey_metrics:
            self.check_stats(counter=[
                (self.metric_type + '.result',
                    ['key:test', 'region:GB', 'fallback_allowed:false',
                     'accuracy:high', 'status:miss']),
            ])

        self.check_raven([('ProgrammingError', db_errors)])
