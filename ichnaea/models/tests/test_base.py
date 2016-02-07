from ichnaea.models.base import HashableDict
from ichnaea.tests.base import TestCase


class Single(HashableDict):

    _fields = ('one', )


class Double(HashableDict):

    _fields = ('one', 'two')


class TestHashableDict(TestCase):

    def test_empty(self):
        single = Single()
        self.assertIs(single.one, None)

    def test_init(self):
        values = {'one': 1, 'two': 2}
        double = Double(**values)
        self.assertEqual(double.one, 1)
        self.assertEqual(double.two, 2)

    def test_no_extra_attributes(self):
        single = Single(one=1, extra=2)
        self.assertEqual(single.one, 1)
        self.assertRaises(AttributeError, getattr, single, 'extra')

    def test_no_positional_args(self):
        self.assertRaises(TypeError, Single, 1)
        self.assertRaises(TypeError, Single, 'one')
        self.assertRaises(TypeError, Double, 1, 2)
        self.assertRaises(TypeError, Double, 'one', 'two')
        with self.assertRaises(TypeError):
            Double(1, two=2)

    def test_attribute_error(self):
        single = Single(one='one')
        self.assertEqual(single.one, 'one')
        self.assertRaises(AttributeError, getattr, single, 'two')

    def test_hashable(self):
        single = Single(one=1)
        singles = {
            single: 1,
            Single(one=2): 2,
        }
        self.assertEqual(len(singles), 2)
        self.assertEqual(singles[single], 1)
        another = Single(one=1)
        self.assertEqual(singles[another], 1)

    def test_compare(self):
        empty = Single()
        one = Single(one=1)
        two1 = Single(one=2)
        two2 = Single(one=2)
        double = Double(one=1)

        self.assertNotEqual(empty, one)
        self.assertNotEqual(one, two1)
        self.assertNotEqual(two1, empty)
        self.assertEqual(two1, two2)
        self.assertNotEqual(double, one)
        self.assertNotEqual(empty, None)
        self.assertNotEqual(empty, {})
        self.assertNotEqual(empty, object())
