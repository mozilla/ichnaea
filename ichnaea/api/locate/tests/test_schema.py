from colander import Invalid

from ichnaea.api.locate import schema
from ichnaea.models import constants
from ichnaea.models.constants import Radio
from ichnaea.tests.base import TestCase


class BaseCellTest(TestCase):

    def compare(self, name, value, expect, radio='lte'):
        if name == 'radioType':
            radio = value
        else:
            radio = radio
        item = {
            name: value,
            'radioType': radio,
        }
        self.assertEqual(self.sample(item)[name], expect)

    def sample(self, item):
        value = {
            'radioType': 'lte',
            'mobileCountryCode': 262,
            'mobileNetworkCode': 1,
            'locationAreaCode': 2,
            'cellId': 3,
        }
        value.update(item)
        return self._schema.deserialize(value)


class TestValidCellAreaLookupSchema(BaseCellTest):

    _schema = schema.ValidCellAreaLookupSchema()

    def test_radio(self):
        self.compare('radioType', 'gsm', Radio.gsm)
        self.compare('radioType', 'wcdma', Radio.wcdma)
        self.compare('radioType', 'lte', Radio.lte)
        self.assertRaises(Invalid, self.sample, {'radioType': 'GSM'})

    def test_mcc(self):
        field = 'mobileCountryCode'
        self.compare(field, 262, 262)
        self.assertRaises(Invalid, self.sample, {field: 101})

    def test_mnc(self):
        field = 'mobileNetworkCode'
        max_mnc = constants.MAX_MNC
        self.compare(field, max_mnc, max_mnc)
        self.assertRaises(Invalid, self.sample, {field: max_mnc + 1})

    def test_asu(self):
        max_lte_asu = constants.MAX_CELL_ASU[Radio.lte]
        self.compare('asu', max_lte_asu, None, 'gsm')
        self.compare('asu', max_lte_asu, max_lte_asu, 'lte')
        self.assertEqual(
            self.sample({'radioType': 'gsm', 'asu': 15})['signalStrength'],
            -83)
        self.assertEqual(
            self.sample({'radioType': 'wcdma', 'asu': 15})['signalStrength'],
            -101)
        self.assertEqual(
            self.sample({'radioType': 'lte', 'asu': 15})['signalStrength'],
            -125)

    def test_asu_signal(self):
        self.compare('signalStrength', -80, -80)
        item = self.sample({'asu': -80})
        self.assertEqual(item['asu'], None)
        self.assertEqual(item['signalStrength'], -80)

    def test_signal(self):
        max_lte_signal = constants.MAX_CELL_SIGNAL[Radio.lte]
        self.compare('signalStrength', max_lte_signal, None, 'gsm')
        self.compare('signalStrength', max_lte_signal, max_lte_signal, 'lte')


class TestValidCellLookupSchema(BaseCellTest):

    _schema = schema.ValidCellLookupSchema()

    def test_radio(self):
        item = self.sample({'radioType': 'gsm',
                            'cellId': constants.MAX_CID_GSM + 1})
        self.assertEqual(item['cellId'], constants.MAX_CID_GSM + 1)
        self.assertEqual(item['radioType'], Radio.wcdma)

    def test_psc(self):
        field = 'primaryScramblingCode'
        max_psc = constants.MAX_PSC_LTE
        self.compare(field, max_psc, max_psc, radio='lte')
        self.compare(field, max_psc + 1, None, radio='lte')


class TestValidWifiLookupSchema(TestCase):

    _schema = schema.ValidWifiLookupSchema()

    def compare(self, name, value, expect):
        self.assertEqual(self.sample(**{name: value})[name], expect)

    def sample(self, **values):
        value = {
            'macAddress': 'abcdef123456',
        }
        value.update(values)
        return self._schema.deserialize(value)

    def test_channel(self):
        self.compare('channel', 1, 1)
        self.compare('channel', 36, 36)

    def test_channel_frequency(self):
        self.assertEqual(self.sample(channel=0, frequency=10)['channel'], None)
        self.assertEqual(self.sample(channel=0, frequency=2427)['channel'], 4)
        self.assertEqual(self.sample(channel=1, frequency=2000)['channel'], 1)
        self.assertEqual(self.sample(channel=1, frequency=2427)['channel'], 1)

    def test_frequency(self):
        self.assertEqual(self.sample(frequency=2411)['channel'], None)
        self.assertEqual(self.sample(frequency=2412)['channel'], 1)
        self.assertEqual(self.sample(frequency=2484)['channel'], 14)
        self.assertEqual(self.sample(frequency=2473)['channel'], None)
        self.assertEqual(self.sample(frequency=5168)['channel'], None)
        self.assertEqual(self.sample(frequency=5170)['channel'], 34)
        self.assertEqual(self.sample(frequency=5825)['channel'], 165)
        self.assertEqual(self.sample(frequency=5826)['channel'], None)
