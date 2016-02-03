from ichnaea.models.base import HashableDict
from ichnaea.models.hashkey import (
    HashKeyQueryMixin,
)
from ichnaea.tests.base import TestCase


class Single(HashableDict):

    _fields = ('one', )


class Double(HashableDict):

    _fields = ('one', 'two')


class SingleMixin(HashKeyQueryMixin):

    _hashkey_cls = Single


class DoubleMixin(HashKeyQueryMixin):

    _hashkey_cls = Double


class TestHashKeyQueryMixin(TestCase):

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
