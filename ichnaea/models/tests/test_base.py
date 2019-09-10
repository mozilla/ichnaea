import pytest

from ichnaea.models.base import HashableDict


class Single(HashableDict):

    _fields = ("one",)


class Double(HashableDict):

    _fields = ("one", "two")


class TestHashableDict(object):
    def test_empty(self):
        single = Single()
        assert single.one is None

    def test_init(self):
        values = {"one": 1, "two": 2}
        double = Double(**values)
        assert double.one == 1
        assert double.two == 2

    def test_no_extra_attributes(self):
        single = Single(one=1, extra=2)
        assert single.one == 1
        with pytest.raises(AttributeError):
            getattr(single, "extra")

    def test_no_positional_args(self):
        pytest.raises(TypeError, Single, 1)
        pytest.raises(TypeError, Single, "one")
        pytest.raises(TypeError, Double, 1, 2)
        pytest.raises(TypeError, Double, "one", "two")
        with pytest.raises(TypeError):
            Double(1, two=2)

    def test_attribute_error(self):
        single = Single(one="one")
        assert single.one == "one"
        with pytest.raises(AttributeError):
            getattr(single, "two")

    def test_hashable(self):
        single = Single(one=1)
        singles = {single: 1, Single(one=2): 2}
        assert len(singles) == 2
        assert singles[single] == 1
        another = Single(one=1)
        assert singles[another] == 1

    def test_compare(self):
        empty = Single()
        one = Single(one=1)
        two1 = Single(one=2)
        two2 = Single(one=2)
        double = Double(one=1)

        assert empty != one
        assert one != two1
        assert two1 != empty
        assert two1 == two2
        assert double != one
        assert empty is not None
        assert empty != {}
        assert empty != object()
