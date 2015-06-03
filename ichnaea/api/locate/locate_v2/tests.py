from uuid import uuid1

from sqlalchemy import text

from ichnaea.models import (
    ApiKey,
    Radio,
)
from ichnaea.tests.base import AppTestCase
from ichnaea.tests.factories import (
    CellFactory,
    CellAreaFactory,
    WifiFactory,
)
from ichnaea import util


class TestLocateV2(AppTestCase):

    def setUp(self):
        super(TestLocateV2, self).setUp()
        self.url = '/v1/geolocate'
        self.metric = 'geolocate'
        self.metric_url = 'request.v1.geolocate'

    def test_ok_cell(self):
        cell = CellFactory()
        self.session.flush()

        res = self.app.post_json(
            '%s?key=test' % self.url, {
                'radioType': cell.radio.name,
                'cellTowers': [{
                    'mobileCountryCode': cell.mcc,
                    'mobileNetworkCode': cell.mnc,
                    'locationAreaCode': cell.lac,
                    'cellId': cell.cid,
                    'signalStrength': -70,
                    'timingAdvance': 1},
                ]},
            status=200)

        self.check_stats(
            counter=[self.metric_url + '.200',
                     self.metric + '.api_key.test',
                     self.metric + '.api_log.test.cell_hit']
        )

        self.assertEqual(res.content_type, 'application/json')
        self.assertEqual(res.json, {'location': {'lat': cell.lat,
                                                 'lng': cell.lon},
                                    'accuracy': cell.range})

    def test_ok_cellarea(self):
        cell = CellAreaFactory()
        self.session.flush()

        res = self.app.post_json(
            '%s?key=test' % self.url, {
                'radioType': cell.radio.name,
                'cellTowers': [{
                    'mobileCountryCode': cell.mcc,
                    'mobileNetworkCode': cell.mnc,
                    'locationAreaCode': cell.lac,
                    'signalStrength': -70,
                    'timingAdvance': 1},
                ]},
            status=200)

        self.check_stats(
            counter=[self.metric_url + '.200',
                     self.metric + '.api_key.test',
                     self.metric + '.api_log.test.cell_lac_hit']
        )

        self.assertEqual(res.content_type, 'application/json')
        self.assertEqual(res.json, {'location': {'lat': cell.lat,
                                                 'lng': cell.lon},
                                    'accuracy': cell.range})

    def test_ok_cellarea_when_lacf_enabled(self):
        cell = CellAreaFactory()
        self.session.flush()

        res = self.app.post_json(
            '%s?key=test' % self.url,
            {
                'radioType': cell.radio.name,
                'cellTowers': [{
                    'mobileCountryCode': cell.mcc,
                    'mobileNetworkCode': cell.mnc,
                    'locationAreaCode': cell.lac,
                    'signalStrength': -70,
                    'timingAdvance': 1},
                ],
                'fallbacks': {
                    'lacf': 1,
                },
            },
            status=200)

        self.check_stats(
            counter=[self.metric_url + '.200',
                     self.metric + '.api_key.test',
                     self.metric + '.api_log.test.cell_lac_hit']
        )

        self.assertEqual(res.content_type, 'application/json')
        self.assertEqual(res.json, {'location': {'lat': cell.lat,
                                                 'lng': cell.lon},
                                    'accuracy': cell.range})

    def test_cellarea_not_found_when_lacf_disabled(self):
        cell = CellAreaFactory()
        self.session.flush()

        res = self.app.post_json(
            '%s?key=test' % self.url,
            {
                'radioType': cell.radio.name,
                'cellTowers': [{
                    'mobileCountryCode': cell.mcc,
                    'mobileNetworkCode': cell.mnc,
                    'locationAreaCode': cell.lac,
                    'signalStrength': -70,
                    'timingAdvance': 1},
                ],
                'fallbacks': {
                    'lacf': 0,
                },
            },
            status=404)

        self.check_stats(
            counter=[self.metric_url + '.404',
                     self.metric + '.api_key.test']
        )

        self.assertEqual(res.content_type, 'application/json')
        self.assertEqual(
            res.json, {'error': {
                'errors': [{
                    'domain': 'geolocation',
                    'reason': 'notFound',
                    'message': 'Not found',
                }],
                'code': 404,
                'message': 'Not found'
            }}
        )

    def test_ok_partial_cell(self):
        session = self.session
        cell = CellFactory()
        session.flush()

        res = self.app.post_json(
            '%s?key=test' % self.url, {
                'cellTowers': [{
                    'radioType': cell.radio.name,
                    'mobileCountryCode': cell.mcc,
                    'mobileNetworkCode': cell.mnc,
                    'locationAreaCode': cell.lac,
                    'cellId': cell.cid,
                    'psc': cell.psc}, {
                    'radioType': cell.radio.name,
                    'mobileCountryCode': cell.mcc,
                    'mobileNetworkCode': cell.mnc,
                    'psc': cell.psc + 1,
                }]},
            status=200)

        self.assertEqual(res.content_type, 'application/json')
        self.assertEqual(res.json, {'location': {'lat': cell.lat,
                                                 'lng': cell.lon},
                                    'accuracy': cell.range})

    def test_ok_wifi(self):
        wifi = WifiFactory()
        offset = 0.0001
        wifis = [
            wifi,
            WifiFactory(lat=wifi.lat + offset),
            WifiFactory(lat=wifi.lat + offset * 2),
            WifiFactory(lat=None, lon=None),
        ]
        self.session.flush()
        res = self.app.post_json(
            '%s?key=test' % self.url, {
                'wifiAccessPoints': [
                    {'macAddress': wifis[0].key, 'channel': 6},
                    {'macAddress': wifis[1].key, 'frequency': 2437},
                    {'macAddress': wifis[2].key, 'signalStrength': -77},
                    {'macAddress': wifis[3].key, 'signalToNoiseRatio': 13},
                ]},
            status=200)
        self.check_stats(
            counter=[self.metric + '.api_key.test',
                     self.metric + '.api_log.test.wifi_hit'])
        self.assertEqual(res.content_type, 'application/json')
        self.assertEqual(res.json, {'location': {'lat': wifi.lat + offset,
                                                 'lng': wifi.lon},
                                    'accuracy': wifi.range})

    def test_wifi_not_found(self):
        wifis = WifiFactory.build_batch(2)
        res = self.app.post_json(
            '%s?key=test' % self.url, {
                'wifiAccessPoints': [
                    {'macAddress': wifis[0].key},
                    {'macAddress': wifis[1].key},
                ]},
            status=404)
        self.assertEqual(res.content_type, 'application/json')
        self.assertEqual(
            res.json, {'error': {
                'errors': [{
                    'domain': 'geolocation',
                    'reason': 'notFound',
                    'message': 'Not found',
                }],
                'code': 404,
                'message': 'Not found'
            }}
        )

        # Make sure to get two counters, a timer, and no traceback
        self.check_stats(
            counter=[self.metric + '.api_key.test',
                     self.metric + '.api_log.test.wifi_miss',
                     self.metric_url + '.404'],
            timer=[self.metric_url])

    def test_cell_mcc_mnc_strings(self):
        # mcc and mnc are officially defined as strings, where '01' is
        # different from '1'. In practice many systems ours included treat
        # them as integers, so both of these are encoded as 1 instead.
        # Some clients sends us these values as strings, some as integers,
        # so we want to make sure we support both.
        cell = CellFactory(mnc=1)
        self.session.flush()

        res = self.app.post_json(
            '%s?key=test' % self.url, {
                'cellTowers': [{
                    'radioType': cell.radio.name,
                    'mobileCountryCode': str(cell.mcc),
                    'mobileNetworkCode': '01',
                    'locationAreaCode': cell.lac,
                    'cellId': cell.cid},
                ]},
            status=200)

        self.assertEqual(res.content_type, 'application/json')
        self.assertEqual(res.json, {'location': {'lat': cell.lat,
                                                 'lng': cell.lon},
                                    'accuracy': cell.range})

    def test_geoip_fallback(self):
        london = self.geoip_data['London']
        wifis = WifiFactory.build_batch(4)
        res = self.app.post_json(
            '%s?key=test' % self.url,
            {'wifiAccessPoints': [
                {'macAddress': wifis[0].key},
                {'macAddress': wifis[1].key},
                {'macAddress': wifis[2].key},
                {'macAddress': wifis[3].key},
            ]},
            extra_environ={'HTTP_X_FORWARDED_FOR': london['ip']},
            status=200)
        self.assertEqual(res.content_type, 'application/json')
        self.assertEqual(res.json, {'location': {'lat': london['latitude'],
                                                 'lng': london['longitude']},
                                    'accuracy': london['accuracy']})

    def test_empty_request_means_geoip(self):
        london = self.geoip_data['London']
        res = self.app.post_json(
            '%s?key=test' % self.url, {},
            extra_environ={'HTTP_X_FORWARDED_FOR': london['ip']},
            status=200)
        self.assertEqual(res.content_type, 'application/json')
        self.assertEqual(res.json, {'location': {'lat': london['latitude'],
                                                 'lng': london['longitude']},
                                    'accuracy': london['accuracy']})

    def test_incomplete_request_means_geoip(self):
        london = self.geoip_data['London']
        res = self.app.post_json(
            '%s?key=test' % self.url, {'wifiAccessPoints': []},
            extra_environ={'HTTP_X_FORWARDED_FOR': london['ip']},
            status=200)
        self.assertEqual(res.content_type, 'application/json')
        self.assertEqual(res.json, {'location': {'lat': london['latitude'],
                                                 'lng': london['longitude']},
                                    'accuracy': london['accuracy']})

    def test_parse_error(self):
        res = self.app.post('%s?key=test' % self.url, '\xae', status=400)
        self.assertEqual(res.content_type, 'application/json')
        self.assertEqual(
            res.json, {'error': {
                'errors': [{
                    'domain': 'global',
                    'reason': 'parseError',
                    'message': 'Parse Error',
                }],
                'code': 400,
                'message': 'Parse Error'
            }})

        self.check_stats(counter=[self.metric + '.api_key.test'])

    def test_no_api_key(self):
        cell = CellFactory()
        self.session.flush()

        res = self.app.post_json(
            self.url, {
                'cellTowers': [{
                    'radioType': cell.radio.name,
                    'mobileCountryCode': cell.mcc,
                    'mobileNetworkCode': cell.mnc,
                    'locationAreaCode': cell.lac,
                    'cellId': cell.cid},
                ]
            },
            status=400)
        self.assertEqual(res.content_type, 'application/json')
        self.assertEqual(u'Invalid API key', res.json['error']['message'])

        self.check_stats(
            counter=[self.metric + '.no_api_key'])

    def test_unknown_api_key(self):
        cell = CellFactory()
        self.session.flush()

        res = self.app.post_json(
            '%s?key=unknown_key' % self.url, {
                'radioType': cell.radio.name,
                'cellTowers': [
                    {'mobileCountryCode': cell.mcc,
                     'mobileNetworkCode': cell.mnc,
                     'locationAreaCode': cell.lac,
                     'cellId': cell.cid},
                ]
            },
            status=400)
        self.assertEqual(res.content_type, 'application/json')
        self.assertEqual(u'Invalid API key', res.json['error']['message'])

        self.check_stats(
            counter=[self.metric + '.unknown_api_key'])

    def test_api_key_limit(self):
        london = self.geoip_data['London']
        api_key = uuid1().hex
        self.session.add(ApiKey(valid_key=api_key, maxreq=5, shortname='dis'))
        self.session.flush()

        # exhaust today's limit
        dstamp = util.utcnow().strftime('%Y%m%d')
        key = 'apilimit:%s:%s' % (api_key, dstamp)
        self.redis_client.incr(key, 10)

        res = self.app.post_json(
            '%s?key=%s' % (self.url, api_key), {},
            extra_environ={'HTTP_X_FORWARDED_FOR': london['ip']},
            status=403)

        errors = res.json['error']['errors']
        self.assertEqual(errors[0]['reason'], 'dailyLimitExceeded')

    def test_lte_radio(self):
        cell = CellFactory(radio=Radio.lte)
        self.session.flush()

        res = self.app.post_json(
            '%s?key=test' % self.url, {
                'cellTowers': [{
                    'radio': cell.radio.name,
                    'mobileCountryCode': cell.mcc,
                    'mobileNetworkCode': cell.mnc,
                    'locationAreaCode': cell.lac,
                    'cellId': cell.cid},
                ]},
            status=200)

        self.check_stats(
            counter=[self.metric_url + '.200', self.metric + '.api_key.test'])

        self.assertEqual(res.content_type, 'application/json')
        location = res.json['location']
        self.assertAlmostEquals(location['lat'], cell.lat)
        self.assertAlmostEquals(location['lng'], cell.lon)
        self.assertEqual(res.json['accuracy'], cell.range)

    def test_ok_cell_radio_in_celltowers(self):
        # This test covers a bug related to FxOS calling the
        # geolocate API incorrectly.
        cell = CellFactory()
        self.session.flush()

        res = self.app.post_json(
            '%s?key=test' % self.url, {
                'cellTowers': [
                    {'radio': cell.radio.name,
                     'mobileCountryCode': cell.mcc,
                     'mobileNetworkCode': cell.mnc,
                     'locationAreaCode': cell.lac,
                     'cellId': cell.cid},
                ]},
            status=200)

        self.assertEqual(res.json, {'location': {'lat': cell.lat,
                                                 'lng': cell.lon},
                                    'accuracy': cell.range})

    def test_ok_cell_radiotype_in_celltowers(self):
        # This test covers an extension to the geolocate API
        cell = CellFactory()
        self.session.flush()

        res = self.app.post_json(
            '%s?key=test' % self.url, {
                'cellTowers': [
                    {'radioType': cell.radio.name,
                     'mobileCountryCode': cell.mcc,
                     'mobileNetworkCode': cell.mnc,
                     'locationAreaCode': cell.lac,
                     'cellId': cell.cid},
                ]},
            status=200)

        self.assertEqual(res.json, {'location': {'lat': cell.lat,
                                                 'lng': cell.lon},
                                    'accuracy': cell.range})

    def test_ok_cell_radio_in_celltowers_dupes(self):
        # This test covers a bug related to FxOS calling the
        # geolocate API incorrectly.
        cell = CellFactory()
        self.session.flush()
        res = self.app.post_json(
            '%s?key=test' % self.url, {
                'cellTowers': [
                    {'radio': cell.radio.name,
                     'mobileCountryCode': cell.mcc,
                     'mobileNetworkCode': cell.mnc,
                     'locationAreaCode': cell.lac,
                     'cellId': cell.cid},
                    {'radio': cell.radio.name,
                     'mobileCountryCode': cell.mcc,
                     'mobileNetworkCode': cell.mnc,
                     'locationAreaCode': cell.lac,
                     'cellId': cell.cid},
                ]},
            status=200)
        self.assertEqual(res.json, {'location': {'lat': cell.lat,
                                                 'lng': cell.lon},
                                    'accuracy': cell.range})

    def test_inconsistent_cell_radio_in_towers(self):
        cell = CellFactory(radio=Radio.umts, range=15000)
        cell2 = CellFactory(radio=Radio.gsm, range=35000,
                            lat=cell.lat + 0.0002, lon=cell.lon)
        self.session.flush()

        res = self.app.post_json(
            '%s?key=test' % self.url, {
                'radioType': Radio.cdma.name,
                'cellTowers': [
                    {'radio': 'wcdma',
                     'mobileCountryCode': cell.mcc,
                     'mobileNetworkCode': cell.mnc,
                     'locationAreaCode': cell.lac,
                     'cellId': cell.cid},
                    {'radio': cell2.radio.name,
                     'mobileCountryCode': cell2.mcc,
                     'mobileNetworkCode': cell2.mnc,
                     'locationAreaCode': cell2.lac,
                     'cellId': cell2.cid},
                ]},
            status=200)

        location = res.json['location']
        self.assertAlmostEquals(location['lat'], cell.lat)
        self.assertAlmostEquals(location['lng'], cell.lon)
        self.assertEqual(res.json['accuracy'], cell.range)

    def test_inconsistent_cell_radio_type_in_towers(self):
        cell = CellFactory(radio=Radio.umts, range=15000)
        cell2 = CellFactory(radio=Radio.gsm, range=35000,
                            lat=cell.lat + 0.0002, lon=cell.lon)
        self.session.flush()

        res = self.app.post_json(
            '%s?key=test' % self.url, {
                'radioType': Radio.cdma.name,
                'cellTowers': [
                    {'radio': 'cdma',
                     'radioType': 'wcdma',
                     'mobileCountryCode': cell.mcc,
                     'mobileNetworkCode': cell.mnc,
                     'locationAreaCode': cell.lac,
                     'cellId': cell.cid},
                    {'radioType': cell2.radio.name,
                     'mobileCountryCode': cell2.mcc,
                     'mobileNetworkCode': cell2.mnc,
                     'locationAreaCode': cell2.lac,
                     'cellId': cell2.cid},
                ]},
            status=200)

        location = res.json['location']
        self.assertAlmostEquals(location['lat'], cell.lat)
        self.assertAlmostEquals(location['lng'], cell.lon)
        self.assertEqual(res.json['accuracy'], cell.range)


class TestLocateV2Errors(AppTestCase):
    # this is a standalone class to ensure DB isolation for dropping tables

    def tearDown(self):
        self.setup_tables(self.db_rw.engine)
        super(TestLocateV2Errors, self).tearDown()

    def test_database_error(self):
        london = self.geoip_data['London']
        session = self.session
        stmt = text('drop table wifi;')
        session.execute(stmt)
        stmt = text('drop table cell;')
        session.execute(stmt)
        cell = CellFactory.build()
        wifis = WifiFactory.build_batch(2)

        res = self.app.post_json(
            '/v1/geolocate?key=test', {
                'cellTowers': [{
                    'radioType': cell.radio.name,
                    'mobileCountryCode': cell.mcc,
                    'mobileNetworkCode': cell.mnc,
                    'locationAreaCode': cell.lac,
                    'cellId': cell.cid},
                ],
                'wifiAccessPoints': [
                    {'macAddress': wifis[0].key},
                    {'macAddress': wifis[1].key},
                ]},
            extra_environ={'HTTP_X_FORWARDED_FOR': london['ip']},
            status=200)

        self.assertEqual(res.content_type, 'application/json')
        self.assertEqual(res.json, {'location': {'lat': london['latitude'],
                                                 'lng': london['longitude']},
                                    'accuracy': london['accuracy']})

        self.check_stats(
            timer=['request.v1.geolocate'],
            counter=[
                'request.v1.geolocate.200',
                'geolocate.geoip_hit',
            ])
        self.check_raven([('ProgrammingError', 2)])
