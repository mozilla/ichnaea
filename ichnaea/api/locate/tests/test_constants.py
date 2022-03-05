import pytest

from ichnaea.api.locate.constants import DataAccuracy


class TestDataAccuracy(object):
    def test_compare(self):
        assert DataAccuracy.high < DataAccuracy.medium
        assert DataAccuracy.high < DataAccuracy.low
        assert DataAccuracy.medium < DataAccuracy.low
        assert DataAccuracy.medium != DataAccuracy.high
        assert DataAccuracy.low == DataAccuracy.low
        assert DataAccuracy.low < DataAccuracy.none
        assert not DataAccuracy.none == "ab"

    def test_compare_number(self):
        assert DataAccuracy.none == float("inf")
        assert DataAccuracy.low > 50000
        assert DataAccuracy.low > 50000.0
        assert DataAccuracy.medium == 50000
        assert DataAccuracy.medium >= 50000.0
        assert DataAccuracy.medium <= 50000
        assert not DataAccuracy.medium != 50000.0
        assert 500.0 <= DataAccuracy.high
        assert 500.1 > DataAccuracy.high

    def test_uncomparable(self):
        with pytest.raises(TypeError):
            DataAccuracy.low < object()
        with pytest.raises(TypeError):
            DataAccuracy.low >= "ab"
        with pytest.raises(TypeError):
            DataAccuracy.low > DataAccuracy

    def test_from_number(self):
        assert DataAccuracy.from_number(1) == DataAccuracy.high
        assert DataAccuracy.from_number(-0.1) == DataAccuracy.high
        assert DataAccuracy.from_number(500) == DataAccuracy.high
        assert DataAccuracy.from_number(500.1) == DataAccuracy.medium
        assert DataAccuracy.from_number(10**5) == DataAccuracy.low
        assert DataAccuracy.from_number(10**9) == DataAccuracy.none
        with pytest.raises(TypeError):
            DataAccuracy.from_number(None)
        with pytest.raises(ValueError):
            DataAccuracy.from_number("ab")

    def test_hash(self):
        accuracies = {
            DataAccuracy.none: 0,
            DataAccuracy.low: 1,
            DataAccuracy.medium: 2,
            DataAccuracy.high: 3,
        }
        assert set(accuracies.values()) == set([0, 1, 2, 3])
