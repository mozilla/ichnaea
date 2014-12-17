import math
from datetime import datetime
from pytz import UTC

from ichnaea.data.constants import MIN_LAT, MAX_LAT


def utcnow():
    return datetime.utcnow().replace(microsecond=0, tzinfo=UTC)


def bound(low, val, high):
    assert low <= high
    return max(low, min(val, high))


def add_meters_to_latitude(lat, distance):
    # A suitable estimate for surface level calculations is
    # 111,111m = 1 degree latitude
    new_lat = lat + (distance/111111.0)
    return bound(MIN_LAT, new_lat, MAX_LAT)


def add_meters_to_longitude(lat, lon, distance):
    # A suitable estimate for surface level calculations is
    # 111,111m = 1 degree latitude
    new_lon = lon + (distance/(math.cos(lat) * 111111.0))
    return bound(-180, new_lon, 180)
