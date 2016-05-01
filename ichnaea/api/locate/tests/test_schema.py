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

    def compare(self, channel, frequency, channel_expect, frequency_expect):
        sample = self.sample(channel=channel, frequency=frequency)
        self.assertEqual(sample['channel'], channel_expect)
        self.assertEqual(sample['frequency'], frequency_expect)

    def sample(self, **values):
        value = {
            'macAddress': 'abcdef123456',
        }
        value.update(values)
        return self._schema.deserialize(value)

    def test_channel(self):
        self.compare(0, None, None, None)
        self.compare(1, None, 1, 2412)
        self.compare(13, None, 13, 2472)
        self.compare(14, None, 14, 2484)
        self.compare(36, None, 36, 5180)
        self.compare(186, None, 186, 4930)
        self.compare(200, None, None, None)

    def test_channel_frequency(self):
        self.compare(None, None, None, None)
        self.compare(4, None, 4, 2427)
        self.compare(None, 2412, 1, 2412)
        self.compare(3, 2412, 3, 2412)

    def test_frequency(self):
        self.compare(None, 2399, None, None)
        self.compare(None, 2412, 1, 2412)
        self.compare(None, 2484, 14, 2484)
        self.compare(None, 4915, 183, 4915)
        self.compare(None, 5180, 36, 5180)
        self.compare(None, 6000, None, None)
