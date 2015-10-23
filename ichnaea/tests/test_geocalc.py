import numpy

from ichnaea.geocalc import (
    aggregate_position,
    bbox,
    distance,
    latitude_add,
    longitude_add,
    random_points,
)
from ichnaea import constants
from ichnaea.tests.base import TestCase


class TestAggregatePosition(TestCase):

    def test_same(self):
        circles = numpy.array([(1.0, 1.0, 100.0)], dtype=numpy.double)
        self.assertEqual(aggregate_position(circles, 100.0),
                         (1.0, 1.0, 100.0))

    def test_minimum(self):
        circles = numpy.array([(1.0, 1.0, 100.0)], dtype=numpy.double)
        self.assertEqual(aggregate_position(circles, 333.0),
                         (1.0, 1.0, 333.0))

    def test_circle_radius(self):
        circles = numpy.array(
            [(1.0, 1.0, 100.0), (1.001, 1.001, 100.0)],
            dtype=numpy.double)
        lat, lon, radius = aggregate_position(circles, 10.0)
        self.assertEqual((lat, lon), (1.0005, 1.0005))
        self.assertAlmostEqual(distance(lat, lon, 1.0, 1.0) + 100.0, radius, 7)


class TestBbox(TestCase):

    def test_null(self):
        lat, lon = (1.0, 1.0)
        self.assertEqual(bbox(lat, lon, 0.0), (lat, lat, lon, lon))

    def test_extremes(self):
        lat, lon = (-90.0, -181.0)
        self.assertEqual(bbox(lat, lon, 0.0),
                         (constants.MIN_LAT, constants.MIN_LAT,
                          constants.MIN_LON, constants.MIN_LON))
        lat, lon = (90.0, 181.0)
        self.assertEqual(bbox(lat, lon, 0.0),
                         (constants.MAX_LAT, constants.MAX_LAT,
                          constants.MAX_LON, constants.MAX_LON))


class TestDistance(TestCase):

    def test_simple_distance(self):
        # This is a simple case where the points are close to each other.
        lat1 = 44.0337065
        lon1 = -79.4908184
        lat2 = 44.0347065
        lon2 = -79.4918184
        delta = distance(lat1, lon1, lat2, lon2)
        self.assertAlmostEqual(delta, 136.9483, 4)

    def test_antipodal(self):
        # Antipodal points (opposite sides of the planet) have a round off
        # error with the standard haversine calculation which is extremely
        # old and assumes we are using fixed precision math instead of IEEE
        # floats.
        self.assertAlmostEqual(distance(90.0, 0.0, -90.0, 0), 20015086.796, 4)

    def test_out_of_max_bounds(self):
        self.assertAlmostEqual(
            distance(-100.0, -186.0, 0.0, 0.0), 8901747.5973, 4)

    def test_non_float(self):
        self.assertAlmostEqual(distance(1.0, 1.0, 1, 1.1), 11117.7991, 4)
        with self.assertRaises(TypeError):
            distance(None, '0.1', 1, 1.1)


class TestLatitudeAdd(TestCase):

    def test_returns_min_lat(self):
        self.assertEqual(latitude_add(1.0, 1.0, -(10 ** 10)),
                         constants.MIN_LAT)

    def test_returns_max_lat(self):
        self.assertEqual(latitude_add(1.0, 1.0, 10 ** 10),
                         constants.MAX_LAT)

    def test_adds_meters_to_latitude(self):
        self.assertAlmostEqual(latitude_add(1.0, 1.0, 1000),
                               1.009000009, 9)


class TestLongitudeAdd(TestCase):

    def test_returns_min_lon(self):
        self.assertEqual(longitude_add(1.0, 1.0, -(10 ** 10)),
                         constants.MIN_LON)

    def test_returns_max_lon(self):
        self.assertEqual(longitude_add(1.0, 1.0, 10 ** 10),
                         constants.MAX_LON)

    def test_adds_meters_to_longitude(self):
        self.assertAlmostEqual(longitude_add(1.0, 1.0, 1000),
                               1.0166573581, 9)


class TestRandomPoints(TestCase):

    def test_null(self):
        points = random_points(0, 0, 20)
        self.assertEqual(type(points), list)
        self.assertEqual(len(points), 2)

    def test_stable(self):
        points1 = random_points(10123, -170234, 1)
        points2 = random_points(10123, -170234, 1)
        points3 = random_points(10124, -170234, 1)
        self.assertEqual(points1, points2)
        self.assertNotEqual(points1, points3)
        self.assertNotEqual(points2, points3)

    def test_num(self):
        self.assertEqual(len(random_points(1, -2, 20)), 2)
        self.assertEqual(len(random_points(1, -2, 6)), 2)
        self.assertEqual(len(random_points(1, -2, 5)), 2)
        self.assertEqual(len(random_points(1, -2, 4)), 4)
        self.assertEqual(len(random_points(1, -2, 1)), 10)
        self.assertEqual(len(random_points(1, -2, 0)), 12)
        self.assertEqual(len(random_points(1, -2, -1)), 12)
        self.assertEqual(len(random_points(1, -2, -10)), 12)

    def test_large(self):
        random_points(90000, 180000, 1)
        random_points(-90000, -180000, 1)
