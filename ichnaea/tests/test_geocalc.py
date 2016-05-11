import pytest

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


class TestBbox(object):

    def test_null(self):
        lat, lon = (1.0, 1.0)
        lat1, lon1, lat2, lon2 = bbox(lat, lon, 0.0)
        assert round(lat1, 7) == lat
        assert round(lon1, 7) == lon
        assert round(lat2, 7) == lat
        assert round(lon2, 7) == lon

    def test_extremes(self):
        lat, lon = (-90.0, -181.0)
        assert (bbox(lat, lon, 0.0) ==
                (constants.MIN_LAT, constants.MIN_LAT,
                 constants.MIN_LON, constants.MIN_LON))
        lat, lon = (90.0, 181.0)
        assert (bbox(lat, lon, 0.0) ==
                (constants.MAX_LAT, constants.MAX_LAT,
                 constants.MAX_LON, constants.MAX_LON))


class TestDestination(object):

    def test_antipodal(self):
        lat, lon = destination(90.0, 0.0, 180.0, 20003931.4586)
        assert round(lat, 7) == -90.0
        assert round(lon, 7) == 0.0

        lat, lon = destination(0.0, 0.0, 89.0, 19902751.0326)
        assert round(lat, 7) == 0.0106671
        assert round(lon, 7) == 178.789547

        lat, lon = destination(0.0, 0.0, 89.7, 19950277.9698)
        assert round(lat, 7) == 0.0009494
        assert round(lon, 7) == 179.2163987

    def test_closeby(self):
        lat, lon = destination(44.0337065, -79.4908184, -0.00071533, 137.0099)
        assert round(lat, 7) == 44.0349396
        assert round(lon, 7) == -79.4908184

        lat, lon = destination(-37.95103, 144.42487, 306.86816, 54972.271)
        assert round(lat, 7) == -37.6528177
        assert round(lon, 7) == 143.9264977

    def test_negative(self):
        lat, lon = destination(1.0, 1.0, 0.0, 1000)
        assert round(lat, 7) == 1.0090437
        assert round(lon, 7) == 1.0

        lat, lon = destination(1.0, 1.0, 0.0, -1000)
        assert round(lat, 7) == 0.9909563
        assert round(lon, 7) == 1.0

        lat, lon = destination(1.0, 1.0, 90.0, 1000)
        assert round(lat, 7) == 1.0
        assert round(lon, 7) == 1.0089845

        lat, lon = destination(1.0, 1.0, 90.0, -1000)
        assert round(lat, 7) == 1.0
        assert round(lon, 7) == 0.9910155

    def test_out_of_bounds(self):
        lat, lon = destination(-100.0, -186.0, 60.0, 100000.0)
        assert round(lat, 7) == 80.4166734
        assert round(lon, 7) == -181.3373112

        lat, lon = destination(-100.0, -186.0, 60.0, 200000.0)
        assert round(lat, 7) == 80.7657146
        assert round(lon, 7) == -176.2908896


class TestDistance(object):

    dist = distance

    def test_antipodal(self):
        assert round(self.dist(90.0, 0.0, -90.0, 0.0), 4) == 20003931.4586
        assert round(self.dist(0.0, 0.0, 0.5, 179.0), 4) == 19902751.0326
        assert round(self.dist(0.0, 0.0, 0.5, 179.7), 4) == 19950277.9698

    def test_closeby(self):
        assert round(self.dist(
            44.0337065, -79.4908184, 44.0349396, -79.4908184), 4) == 137.0133

    def test_non_float(self):
        assert round(self.dist(1.0, 1.0, 1, 1.1), 4) == 11130.265
        with pytest.raises(TypeError):
            self.dist(None, '0.1', 1, 1.1)

    def test_out_of_bounds(self):
        assert round(self.dist(-100.0, -186.0, 0.0, 0.0), 4) == 11112616.8752


class TestHaversineDistance(object):

    dist = haversine_distance

    def test_antipodal(self):
        assert round(self.dist(90.0, 0.0, -90.0, 0.0), 4) == 20015115.0704
        assert round(self.dist(0.0, 0.0, 0.5, 179.0), 4) == 19890796.4497
        assert round(self.dist(0.0, 0.0, 0.5, 179.7), 4) == 19950277.9698

    def test_closeby(self):
        assert round(self.dist(
            44.0337065, -79.4908184, 44.0349396, -79.4908184), 4) == 137.1147

    def test_out_of_bounds(self):
        assert round(self.dist(-100.0, -186.0, 0.0, 0.0), 4) == 8901760.1724


class TestVincentyDistance(object):

    dist = vincenty_distance

    def test_antipodal(self):
        assert round(self.dist(90.0, 0.0, -90.0, 0.0), 4) == 20003931.4586
        assert round(self.dist(0.0, 0.0, 0.5, 179.0), 4) == 19902751.0326
        with pytest.raises(ValueError):
            self.dist(0.0, 0.0, 0.5, 179.7)

    def test_closeby(self):
        assert round(self.dist(
            44.0337065, -79.4908184, 44.0349396, -79.4908184), 4) == 137.0133

    def test_out_of_bounds(self):
        assert round(self.dist(-100.0, -186.0, 0.0, 0.0), 4) == 11112616.8752


class TestLatitudeAdd(object):

    def test_returns_min_lat(self):
        assert latitude_add(-85.0, 0.0, -1000000) == constants.MIN_LAT

    def test_returns_max_lat(self):
        assert latitude_add(85.0, 0.0, 1000000) == constants.MAX_LAT

    def test_adds_meters_to_latitude(self):
        assert round(latitude_add(1.0, 1.0, 1000), 7) == 1.0090437


class TestLongitudeAdd(object):

    def test_returns_min_lon(self):
        assert longitude_add(0.0, -179.0, -1000000) == constants.MIN_LON

    def test_returns_max_lon(self):
        assert longitude_add(0.0, 179.0, 1000000) == constants.MAX_LON

    def test_adds_meters_to_longitude(self):
        assert round(longitude_add(1.0, 1.0, 1000), 7) == 1.0089845


class TestRandomPoints(object):

    def test_null(self):
        points = random_points(0, 0, 20)
        assert type(points) is list
        assert len(points) == 2

    def test_stable(self):
        points1 = random_points(10123, -170234, 1)
        points2 = random_points(10123, -170234, 1)
        points3 = random_points(10124, -170234, 1)
        assert points1 == points2
        assert points1 != points3
        assert points2 != points3

    def test_num(self):
        assert len(random_points(1, -2, 20)) == 2
        assert len(random_points(1, -2, 6)) == 2
        assert len(random_points(1, -2, 5)) == 2
        assert len(random_points(1, -2, 4)) == 4
        assert len(random_points(1, -2, 1)) == 10
        assert len(random_points(1, -2, 0)) == 12
        assert len(random_points(1, -2, -1)) == 12
        assert len(random_points(1, -2, -10)) == 12

    def test_large(self):
        random_points(90000, 180000, 1)
        random_points(-90000, -180000, 1)
