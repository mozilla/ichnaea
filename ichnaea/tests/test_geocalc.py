from ichnaea.geocalc import (
    bbox,
    destination,
    distance,
    haversine_distance,
    vincenty_distance,
    latitude_add,
    longitude_add,
    random_points,
)
from ichnaea import constants
from ichnaea.tests.base import TestCase


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


class TestDestination(TestCase):

    def test_antipodal(self):
        lat, lon = destination(90.0, 0.0, 180.0, 20003931.4586)
        self.assertAlmostEqual(lat, -90.0, 7)
        self.assertAlmostEqual(lon, 0.0, 7)

        lat, lon = destination(0.0, 0.0, 89.0, 19902751.0326)
        self.assertAlmostEqual(lat, 0.0106671, 7)
        self.assertAlmostEqual(lon, 178.789547, 7)

        lat, lon = destination(0.0, 0.0, 89.7, 19950277.9698)
        self.assertAlmostEqual(lat, 0.0009494, 7)
        self.assertAlmostEqual(lon, 179.2163987, 7)

    def test_closeby(self):
        lat, lon = destination(44.0337065, -79.4908184, -0.00071533, 137.0099)
        self.assertAlmostEqual(lat, 44.0349396, 7)
        self.assertAlmostEqual(lon, -79.4908184, 7)

        lat, lon = destination(-37.95103, 144.42487, 306.86816, 54972.271)
        self.assertAlmostEqual(lat, -37.6528177, 7)
        self.assertAlmostEqual(lon, 143.9264977, 7)

    def test_out_of_bounds(self):
        lat, lon = destination(-100.0, -186.0, 60.0, 100000.0)
        self.assertAlmostEqual(lat, 80.4166734, 7)
        self.assertAlmostEqual(lon, -181.3373112, 7)

        lat, lon = destination(-100.0, -186.0, 60.0, 200000.0)
        self.assertAlmostEqual(lat, 80.7657146, 7)
        self.assertAlmostEqual(lon, -176.2908896, 7)


class TestDistance(TestCase):

    dist = distance

    def test_antipodal(self):
        self.assertAlmostEqual(self.dist(
            90.0, 0.0, -90.0, 0.0), 20003931.4586, 4)
        self.assertAlmostEqual(self.dist(
            0.0, 0.0, 0.5, 179.0), 19902751.0326, 4)
        self.assertAlmostEqual(self.dist(
            0.0, 0.0, 0.5, 179.7), 19950277.9698, 4)

    def test_closeby(self):
        self.assertAlmostEqual(self.dist(
            44.0337065, -79.4908184, 44.0349396, -79.4908184), 137.0133, 4)

    def test_non_float(self):
        self.assertAlmostEqual(self.dist(1.0, 1.0, 1, 1.1), 11130.265, 4)
        self.assertRaises(TypeError, self.dist, None, '0.1', 1, 1.1)

    def test_out_of_bounds(self):
        self.assertAlmostEqual(self.dist(
            -100.0, -186.0, 0.0, 0.0), 11112616.8752, 4)


class TestHaversineDistance(TestCase):

    dist = haversine_distance

    def test_antipodal(self):
        self.assertAlmostEqual(self.dist(
            90.0, 0.0, -90.0, 0.0), 20015115.0704, 4)
        self.assertAlmostEqual(self.dist(
            0.0, 0.0, 0.5, 179.0), 19890796.4497, 4)
        self.assertAlmostEqual(self.dist(
            0.0, 0.0, 0.5, 179.7), 19950277.9698, 4)

    def test_closeby(self):
        self.assertAlmostEqual(self.dist(
            44.0337065, -79.4908184, 44.0349396, -79.4908184), 137.1147, 4)

    def test_out_of_bounds(self):
        self.assertAlmostEqual(self.dist(
            -100.0, -186.0, 0.0, 0.0), 8901760.1724, 4)


class TestVincentyDistance(TestCase):

    dist = vincenty_distance

    def test_antipodal(self):
        self.assertAlmostEqual(self.dist(
            90.0, 0.0, -90.0, 0.0), 20003931.4586, 4)
        self.assertAlmostEqual(self.dist(
            0.0, 0.0, 0.5, 179.0), 19902751.0326, 4)
        self.assertRaises(ValueError, self.dist, 0.0, 0.0, 0.5, 179.7)

    def test_closeby(self):
        self.assertAlmostEqual(self.dist(
            44.0337065, -79.4908184, 44.0349396, -79.4908184), 137.0133, 4)

    def test_out_of_bounds(self):
        self.assertAlmostEqual(self.dist(
            -100.0, -186.0, 0.0, 0.0), 11112616.8752, 4)


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
