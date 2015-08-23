"""
Contains helper functions for various geo related calculations.

These are implemented in Cython / C using NumPy.
"""

from libc.math cimport asin, cos, fmin, M_PI, pow, sin, sqrt
from numpy cimport float64_t, ndarray

cdef double EARTH_RADIUS = 6371.0  #: Earth radius in km.


cdef inline double deg2rad(double degrees):
    return degrees * M_PI / 180.0


cpdef ndarray[float64_t, ndim=1] centroid(ndarray[float64_t, ndim=2] points):
    """
    Compute the centroid (average lat and lon) from a set of points
    (two-dimensional lat/lon array).
    """
    return points.mean(axis=0)


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
