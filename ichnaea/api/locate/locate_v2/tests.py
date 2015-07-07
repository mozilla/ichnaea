from uuid import uuid1

from sqlalchemy import text

from ichnaea.models import (
    ApiKey,
    Radio,
)
from ichnaea.api.locate.locate_v2.schema import LocateV2Schema
from ichnaea.api.locate.tests.base import (
    BaseLocateTest,
    CommonLocateTest,
)
from ichnaea.tests.base import AppTestCase, TestCase
from ichnaea.tests.factories import (
    CellFactory,
    CellAreaFactory,
    WifiFactory,
)
from ichnaea import util


class TestLocateV2Schema(TestCase):

    def test_multiple_radio_fields_uses_radioType(self):
        schema = LocateV2Schema()
        data = schema.deserialize({'cellTowers': [{
            'radio': 'gsm',
            'radioType': 'cdma',
        }]})
        self.assertEqual(data['cell'][0]['radio'], 'cdma')
        self.assertFalse('radioType' in data['cell'][0])


class LocateV2Base(BaseLocateTest):

    url = '/v1/geolocate'
    metric = 'geolocate'
    metric_url = 'request.v1.geolocate'

    @property
    def ip_response(self):
        london = self.geoip_data['London']
        return {'location': {'lat': london['latitude'],
                             'lng': london['longitude']},
                'accuracy': london['accuracy']}


class TestLocateV2(AppTestCase, LocateV2Base, CommonLocateTest):

    def check_model_response(self, response, model, fallback=None, **kw):
        expected_names = set(['location', 'accuracy'])

        expected = super(TestLocateV2, self).check_model_response(
            response, model,
            fallback=fallback,
            expected_names=expected_names,
            **kw)

        data = response.json
        location = data['location']
        self.assertAlmostEquals(location['lat'], expected['lat'])
        self.assertAlmostEquals(location['lng'], expected['lon'])
        self.assertAlmostEqual(data['accuracy'], expected['accuracy'])
        if fallback is not None:
            self.assertEqual(data['fallback'], fallback)

    def test_ok_cell(self):
        cell = CellFactory()
        self.session.flush()

        res = self._call(body={
            'radioType': cell.radio.name,
            'cellTowers': [{
                'mobileCountryCode': cell.mcc,
                'mobileNetworkCode': cell.mnc,
                'locationAreaCode': cell.lac,
                'cellId': cell.cid,
                'signalStrength': -70,
                'timingAdvance': 1},
            ]})
        self.check_model_response(res, cell)

        self.check_stats(
            counter=[self.metric_url + '.200',
                     self.metric + '.api_key.test',
                     self.metric + '.api_log.test.cell_hit']
        )

    def test_ok_cellarea(self):
        cell = CellAreaFactory()
        self.session.flush()

        res = self._call(body={
            'radioType': cell.radio.name,
            'cellTowers': [{
                'mobileCountryCode': cell.mcc,
                'mobileNetworkCode': cell.mnc,
                'locationAreaCode': cell.lac,
                'signalStrength': -70,
                'timingAdvance': 1},
            ]})
        self.check_model_response(res, cell)

        self.check_stats(
            counter=[self.metric_url + '.200',
                     self.metric + '.api_key.test',
                     self.metric + '.api_log.test.cell_lac_hit']
        )

    def test_ok_cellarea_when_lacf_enabled(self):
        cell = CellAreaFactory()
        self.session.flush()

        res = self._call(body={
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
            }})
        self.check_model_response(res, cell)

        self.check_stats(
            counter=[self.metric_url + '.200',
                     self.metric + '.api_key.test',
                     self.metric + '.api_log.test.cell_lac_hit']
        )

    def test_cellarea_not_found_when_lacf_disabled(self):
        cell = CellAreaFactory()
        self.session.flush()

        res = self._call(body={
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
            }},
            status=404)
        self.check_response(res, 'not_found')

        self.check_stats(
            counter=[self.metric_url + '.404',
                     self.metric + '.api_key.test']
        )

    def test_ok_partial_cell(self):
        cell = CellFactory()
        self.session.flush()

        res = self._call(body={
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
            }]})
        self.check_model_response(res, cell)

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

        res = self._call(body={
            'wifiAccessPoints': [
                {'macAddress': wifis[0].key, 'channel': 6},
                {'macAddress': wifis[1].key, 'frequency': 2437},
                {'macAddress': wifis[2].key, 'signalStrength': -77},
                {'macAddress': wifis[3].key, 'signalToNoiseRatio': 13},
            ]})
        self.check_model_response(res, wifi, lat=wifi.lat + offset)

        self.check_stats(
            counter=[self.metric + '.api_key.test',
                     self.metric + '.api_log.test.wifi_hit'])

    def test_wifi_not_found(self):
        wifis = WifiFactory.build_batch(2)

        res = self._call(body={
            'wifiAccessPoints': [
                {'macAddress': wifis[0].key},
                {'macAddress': wifis[1].key},
            ]},
            status=404)
        self.check_response(res, 'not_found')

        # Make sure to get two counters, a timer, and no traceback
        self.check_stats(
            counter=[self.metric + '.api_key.test',
                     self.metric + '.api_log.test.wifi_miss',
                     (self.metric_url + '.404', 1)],
            timer=[self.metric_url])

    def test_cell_mcc_mnc_strings(self):
        # mcc and mnc are officially defined as strings, where '01' is
        # different from '1'. In practice many systems ours included treat
        # them as integers, so both of these are encoded as 1 instead.
        # Some clients sends us these values as strings, some as integers,
        # so we want to make sure we support both.
        cell = CellFactory(mnc=1)
        self.session.flush()

        res = self._call(body={
            'cellTowers': [{
                'radioType': cell.radio.name,
                'mobileCountryCode': str(cell.mcc),
                'mobileNetworkCode': '01',
                'locationAreaCode': cell.lac,
                'cellId': cell.cid},
            ]})
        self.check_model_response(res, cell)

    def test_geoip_fallback(self):
        wifis = WifiFactory.build_batch(4)

        res = self._call(body={
            'wifiAccessPoints': [
                {'macAddress': wifis[0].key},
                {'macAddress': wifis[1].key},
                {'macAddress': wifis[2].key},
                {'macAddress': wifis[3].key},
            ]},
            ip=self.test_ip)
        self.check_response(res, 'ok')

    def test_api_key_limit(self):
        api_key = uuid1().hex
        self.session.add(ApiKey(valid_key=api_key, maxreq=5, shortname='dis'))
        self.session.flush()

        # exhaust today's limit
        dstamp = util.utcnow().strftime('%Y%m%d')
        key = 'apilimit:%s:%s' % (api_key, dstamp)
        self.redis_client.incr(key, 10)

        res = self._call(
            body={}, api_key=api_key, ip=self.test_ip, status=403)
        self.check_response(res, 'limit_exceeded')

    def test_lte_radio(self):
        cell = CellFactory(radio=Radio.lte)
        self.session.flush()

        res = self._call(body={
            'cellTowers': [{
                'radio': cell.radio.name,
                'mobileCountryCode': cell.mcc,
                'mobileNetworkCode': cell.mnc,
                'locationAreaCode': cell.lac,
                'cellId': cell.cid},
            ]})
        self.check_model_response(res, cell)

        self.check_stats(
            counter=[self.metric_url + '.200', self.metric + '.api_key.test'])

    def test_ok_cell_radio_in_celltowers(self):
        # This test covers a bug related to FxOS calling the
        # geolocate API incorrectly.
        cell = CellFactory()
        self.session.flush()

        res = self._call(body={
            'cellTowers': [
                {'radio': cell.radio.name,
                 'mobileCountryCode': cell.mcc,
                 'mobileNetworkCode': cell.mnc,
                 'locationAreaCode': cell.lac,
                 'cellId': cell.cid},
            ]})
        self.check_model_response(res, cell)

    def test_ok_cell_radiotype_in_celltowers(self):
        # This test covers an extension to the geolocate API
        cell = CellFactory()
        self.session.flush()

        res = self._call(body={
            'cellTowers': [
                {'radioType': cell.radio.name,
                 'mobileCountryCode': cell.mcc,
                 'mobileNetworkCode': cell.mnc,
                 'locationAreaCode': cell.lac,
                 'cellId': cell.cid},
            ]})
        self.check_model_response(res, cell)

    def test_ok_cell_radio_in_celltowers_dupes(self):
        # This test covers a bug related to FxOS calling the
        # geolocate API incorrectly.
        cell = CellFactory()
        self.session.flush()

        res = self._call(body={
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
            ]})
        self.check_model_response(res, cell)

    def test_inconsistent_cell_radio_in_towers(self):
        cell = CellFactory(radio=Radio.umts, range=15000)
        cell2 = CellFactory(radio=Radio.gsm, range=35000,
                            lat=cell.lat + 0.0002, lon=cell.lon)
        self.session.flush()

        res = self._call(body={
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
            ]})
        self.check_model_response(res, cell)

    def test_inconsistent_cell_radio_type_in_towers(self):
        cell = CellFactory(radio=Radio.umts, range=15000)
        cell2 = CellFactory(radio=Radio.gsm, range=35000,
                            lat=cell.lat + 0.0002, lon=cell.lon)
        self.session.flush()

        res = self._call(body={
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
            ]})
        self.check_model_response(res, cell)


class TestLocateV2Errors(AppTestCase, LocateV2Base):
    # this is a standalone class to ensure DB isolation for dropping tables

    def tearDown(self):
        self.setup_tables(self.db_rw.engine)
        super(TestLocateV2Errors, self).tearDown()

    def test_database_error(self):
        self.session.execute(text('drop table wifi;'))
        self.session.execute(text('drop table cell;'))
        cell = CellFactory.build()
        wifis = WifiFactory.build_batch(2)

        res = self._call(body={
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
            ip=self.test_ip,
            status=200)
        self.check_response(res, 'ok')

        self.check_stats(
            timer=['request.v1.geolocate'],
            counter=[
                'request.v1.geolocate.200',
                'geolocate.geoip_hit',
            ])
        self.check_raven([('ProgrammingError', 2)])
