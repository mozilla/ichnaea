"""
Contains helper functions for various geo related calculations.

These are implemented in Cython / C using NumPy.
"""

from libc.math cimport asin, cos, fmax, fmin, M_PI, pow, sin, sqrt
from numpy cimport double_t, ndarray

import numpy

cdef double EARTH_RADIUS = 6371.0  #: Earth radius in km.
cdef double MAX_LAT = 85.051  #: Max Web Mercator latitude
cdef double MIN_LAT = -85.051  #: Min Web Mercator latitude
cdef double MAX_LON = 180.0  #: Max Web Mercator longitude
cdef double MIN_LON = -180.0  #: Min Web Mercator longitude


cdef inline double deg2rad(double degrees):
    return degrees * M_PI / 180.0


cpdef tuple aggregate_position(ndarray[double_t, ndim=2] circles,
                               double minimum_accuracy):
    """
    Calculate the aggregate position based on a number of circles
    (numpy 3-column arrays of lat/lon/radius).

    Return the position and an accuracy estimate, but at least
    use the minimum_accuracy.
    """
    cdef ndarray[double_t, ndim=2] points
    cdef double lat, lon, radius
    cdef double p_dist, p_lat, p_lon, p_radius

    if len(circles) == 1:
        lat = circles[0][0]
        lon = circles[0][1]
        radius = circles[0][2]
        radius = fmax(radius, minimum_accuracy)
        return (lat, lon, radius)

    points, _ = numpy.hsplit(circles, [2])
    lat, lon = centroid(points)

    # Given the centroid of all the circles, calculate the distance
    # between that point and and all the centers of the provided
    # circles. Add the radius of each of the circles to the distance,
    # to account for the area / uncertainty range of those circles.

    radius = 0.0
    for p_lat, p_lon, p_radius in circles:
        p_dist = distance(lat, lon, p_lat, p_lon) + p_radius
        radius = fmax(radius, p_dist)

    radius = fmax(radius, minimum_accuracy)
    return (lat, lon, radius)


cpdef tuple bbox(double lat, double lon, double meters):
    """
    Return a bounding box around the passed in lat/lon position.
    """
    cdef double max_lat, min_lat, max_lon, min_lon

    max_lat = latitude_add(lat, lon, meters)
    min_lat = latitude_add(lat, lon, -meters)
    max_lon = longitude_add(lat, lon, meters)
    min_lon = longitude_add(lat, lon, -meters)
    return (max_lat, min_lat, max_lon, min_lon)


cpdef tuple centroid(ndarray[double_t, ndim=2] points):
    """
    Compute the centroid (average lat and lon) from a set of points
    (two-dimensional lat/lon array).
    """
    cdef ndarray[double_t, ndim=1] center
    cdef double avg_lat, avg_lon

    center = points.mean(axis=0)
    avg_lat = center[0]
    avg_lon = center[1]
    return (avg_lat, avg_lon)


cpdef int circle_radius(double lat, double lon,
                        double max_lat, double max_lon,
                        double min_lat, double min_lon):
    """
    Compute the maximum distance, in meters, from a (lat, lon) point
    to any of the extreme points of a bounding box.
    """
    cdef ndarray[double_t, ndim=2] points
    cdef double radius

    points = numpy.array([
        (min_lat, min_lon),
        (min_lat, max_lon),
        (max_lat, min_lon),
        (max_lat, max_lon),
    ], dtype=numpy.double)

    radius = max_distance(lat, lon, points)
    return round(radius)


cpdef double distance(double lat1, double lon1, double lat2, double lon2):
    """
    Compute the distance between a pair of lat/longs in meters using
    the haversine calculation. The output distance is in meters.

    References:
      * http://en.wikipedia.org/wiki/Haversine_formula
      * http://www.movable-type.co.uk/scripts/latlong.html

    Accuracy: since the earth is not quite a sphere, there are small
    errors in using spherical geometry; the earth is actually roughly
    ellipsoidal (or more precisely, oblate spheroidal) with a radius
    varying between about 6378km (equatorial) and 6357km (polar),
    and local radius of curvature varying from 6336km (equatorial
    meridian) to 6399km (polar). 6371 km is the generally accepted
    value for the Earth's mean radius. This means that errors from
    assuming spherical geometry might be up to 0.55% crossing the
    equator, though generally below 0.3%, depending on latitude and
    direction of travel. An accuracy of better than 3m in 1km is
    mostly good enough for me, but if you want greater accuracy, you
    could use the Vincenty formula for calculating geodesic distances
    on ellipsoids, which gives results accurate to within 1mm.
    """
    cdef double a, c, dLat, dLon

    dLat = deg2rad(lat2 - lat1) / 2.0
    dLon = deg2rad(lon2 - lon1) / 2.0

    lat1 = deg2rad(lat1)
    lat2 = deg2rad(lat2)

    a = pow(sin(dLat), 2) + cos(lat1) * cos(lat2) * pow(sin(dLon), 2)
    c = asin(fmin(1, sqrt(a)))
    return 1000 * 2 * EARTH_RADIUS * c


cpdef double latitude_add(double lat, double lon, double meters):
    """
    Return a latitude in degrees which is shifted by
    distance in meters.

    The new latitude is bounded by our globally defined
    :data:`ichnaea.constants.MIN_LAT` and
    :data:`ichnaea.constants.MAX_LAT`.

    A suitable estimate for surface level calculations is
    111,111m = 1 degree latitude
    """
    return fmax(MIN_LAT, fmin(lat + (meters / 111111.0), MAX_LAT))


cpdef double longitude_add(double lat, double lon, double meters):
    """
    Return a longitude in degrees which is shifted by
    distance in meters.

    The new longitude is bounded by our globally defined
    :data:`ichnaea.constants.MIN_LON` and
    :data:`ichnaea.constants.MAX_LON`.
    """
    return fmax(MIN_LON, fmin(lon + (meters / (cos(lat) * 111111.0)), MAX_LON))


cpdef double max_distance(double lat, double lon,
                          ndarray[double_t, ndim=2] points):
    """
    Returns the maximum distance from the given lat/lon point to any of
    the provided points in the points array.
    """
    cdef double dist, p_lat, p_lon, result

    result = 0.0
    for p_lat, p_lon in points:
        dist = distance(lat, lon, p_lat, p_lon)
        result = fmax(result, dist)
    return result
