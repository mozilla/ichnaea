from ichnaea.api.locate import schema
from ichnaea.models import constants
from ichnaea.models.constants import Radio
from ichnaea.tests.base import TestCase


class TestValidCellAreaLookupSchema(TestCase):

    _schema = schema.ValidCellAreaLookupSchema()

    def compare(self, name, value, expect, radio='lte'):
        item = {
            name: value,
            'radio': radio,
        }
        self.assertEqual(self.sample(item)[name], expect)

    def sample(self, item):
        value = {
            'radio': 'lte',
            'mcc': 262,
            'mnc': 1,
            'lac': 2,
            'cid': 3,
        }
        value.update(item)
        return self._schema.deserialize(value)

    def test_asu(self):
        max_lte_asu = constants.MAX_CELL_ASU[Radio.lte]
        self.compare('asu', max_lte_asu, None, 'gsm')
        self.compare('asu', max_lte_asu, max_lte_asu, 'lte')
        self.assertEqual(
            self.sample({'radio': 'gsm', 'asu': 15})['signal'], -83)
        self.assertEqual(
            self.sample({'radio': 'wcdma', 'asu': 15})['signal'], -101)
        self.assertEqual(
            self.sample({'radio': 'lte', 'asu': 15})['signal'], -125)

    def test_asu_signal(self):
        self.compare('signal', -80, -80)
        item = self.sample({'asu': -80})
        self.assertEqual(item['asu'], None)
        self.assertEqual(item['signal'], -80)

    def test_signal(self):
        max_lte_signal = constants.MAX_CELL_SIGNAL[Radio.lte]
        self.compare('signal', max_lte_signal, None, 'gsm')
        self.compare('signal', max_lte_signal, max_lte_signal, 'lte')


class TestValidWifiLookupSchema(TestCase):

    _schema = schema.ValidWifiLookupSchema()

    def compare(self, name, value, expect):
        self.assertEqual(self.sample(**{name: value})[name], expect)

    def sample(self, **values):
        value = {
            'mac': 'abcdef123456',
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
