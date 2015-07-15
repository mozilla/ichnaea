from ichnaea.customjson import (
    kombu_dumps,
    kombu_loads,
)
from ichnaea.models.hashkey import (
    HashKey,
    HashKeyMixin,
)
from ichnaea.tests.base import TestCase


class Single(HashKey):

    _fields = ('one', )


class Double(HashKey):

    _fields = ('one', 'two')


class SingleMixin(HashKeyMixin):

    _hashkey_cls = Single


class DoubleMixin(HashKeyMixin):

    _hashkey_cls = Double


class TestHashKey(TestCase):

    def test_empty(self):
        single = Single()
        self.assertIs(single.one, None)
        self.assertTrue('ichnaea.models' in str(single))
        self.assertTrue('Single:' in str(single))

    def test_init(self):
        values = {'one': 1, 'two': 2}
        double = Double(**values)
        self.assertEqual(double.one, 1)
        self.assertEqual(double.two, 2)

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

    def test_json(self):
        double = Double(one=1.1, two='two')
        new_double = kombu_loads(kombu_dumps(double))
        self.assertTrue(isinstance(new_double, Double))
        self.assertEqual(double, new_double)


class TestHashKeyMixin(TestCase):

    def test_single(self):
        mixin = SingleMixin()
        self.assertEqual(mixin.to_hashkey().one, None)
        self.assertEqual(mixin.to_hashkey(one=1).one, 1)
        self.assertEqual(mixin.to_hashkey({'one': 1}).one, 1)
        self.assertEqual(mixin.to_hashkey(**{'one': 1}).one, 1)
        self.assertEqual(mixin.to_hashkey(Single(one=1)).one, 1)

    def test_single_instance(self):
        mixin = SingleMixin()
        self.assertEqual(mixin.hashkey().one, None)
        setattr(mixin, 'one', 1)
        self.assertEqual(mixin.hashkey().one, 1)

    def test_double(self):
        mixin = DoubleMixin()
        self.assertEqual(mixin.to_hashkey().one, None)
        self.assertEqual(mixin.to_hashkey().two, None)
        self.assertEqual(mixin.to_hashkey(two=2).two, 2)
        self.assertEqual(mixin.to_hashkey({'one': 1, 'two': 2}).two, 2)
        self.assertEqual(mixin.to_hashkey(Double(two=2)).two, 2)

    def test_double_instance(self):
        mixin = DoubleMixin()
        self.assertEqual(mixin.hashkey().one, None)
        self.assertEqual(mixin.hashkey().two, None)
        setattr(mixin, 'two', 2)
        self.assertEqual(mixin.hashkey().one, None)
        self.assertEqual(mixin.hashkey().two, 2)
        setattr(mixin, 'one', 1)
        self.assertEqual(mixin.hashkey().one, 1)

    def test_mixed_hashkeys(self):
        single = SingleMixin().to_hashkey(Double(one=1, two=2))
        self.assertEqual(single.one, 1)
        self.assertRaises(AttributeError, getattr, single, 'two')

        double = DoubleMixin().to_hashkey(Single(one=1))
        self.assertEqual(double.one, 1)
        self.assertEqual(double.two, None)

    def test_no_positional_args(self):
        self.assertRaises(TypeError, SingleMixin().to_hashkey, 'one')
        self.assertRaises(TypeError, DoubleMixin().to_hashkey, 'one')
