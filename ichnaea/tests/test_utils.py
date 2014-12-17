from unittest2 import TestCase


from ichnaea.data.constants import MIN_LAT, MAX_LAT
from ichnaea.util import bound, add_meters_to_latitude, add_meters_to_longitude


class TestBound(TestCase):

    def test_max_below_min_raises_exception(self):
        with self.assertRaises(Exception):
            bound(0, 0, -1)

    def test_returns_between_min_max(self):
        self.assertEqual(bound(0, 1, 2), 1)

    def test_returns_below_max(self):
        self.assertEqual(bound(0, 3, 2), 2)

    def test_returns_above_min(self):
        self.assertEqual(bound(0, -1, 2), 0)


class TestAddMetersToLatitude(TestCase):

    def test_returns_min_lat(self):
        self.assertEqual(add_meters_to_latitude(1.0, -(10**10)), MIN_LAT)

    def test_returns_max_lat(self):
        self.assertEqual(add_meters_to_latitude(1.0, 10**10), MAX_LAT)

    def test_adds_meters_to_latitude(self):
        self.assertEqual(add_meters_to_latitude(1.0, 1000), 1.009000009000009)


class TestAddMetersToLongitude(TestCase):

    def test_returns_min_lon(self):
        self.assertEqual(add_meters_to_longitude(1.0, 1.0, -(10**10)), -180)

    def test_returns_max_lon(self):
        self.assertEqual(add_meters_to_longitude(1.0, 1.0, 10**10), 180)

    def test_adds_meters_to_longitude(self):
        self.assertEqual(add_meters_to_longitude(1.0, 1.0, 1000),
                         1.0166573581164864)
