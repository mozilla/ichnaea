from ichnaea.api.locate.constants import DataAccuracy
from ichnaea.tests.base import TestCase


class DataAccuracyTest(TestCase):

    def test_compare(self):
        self.assertTrue(DataAccuracy.high < DataAccuracy.medium)
        self.assertTrue(DataAccuracy.high < DataAccuracy.low)
        self.assertTrue(DataAccuracy.medium < DataAccuracy.low)
        self.assertTrue(DataAccuracy.medium != DataAccuracy.high)
        self.assertTrue(DataAccuracy.low == DataAccuracy.low)
        self.assertFalse(DataAccuracy.low == 'ab')

    def test_compare_number(self):
        self.assertTrue(DataAccuracy.low > 50000)
        self.assertTrue(DataAccuracy.low > 50000.0)
        self.assertTrue(DataAccuracy.medium == 40000)
        self.assertTrue(DataAccuracy.medium >= 40000.0)
        self.assertTrue(DataAccuracy.medium <= 40000)
        self.assertFalse(DataAccuracy.medium != 40000.0)
        self.assertTrue(500.0 <= DataAccuracy.high)
        self.assertFalse(1000.1 <= DataAccuracy.high)

    def test_uncomparable(self):
        with self.assertRaises(TypeError):
            DataAccuracy.low < object()
        with self.assertRaises(TypeError):
            DataAccuracy.low >= 'ab'
        with self.assertRaises(TypeError):
            DataAccuracy.low > DataAccuracy
