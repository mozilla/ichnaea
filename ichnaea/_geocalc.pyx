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
    the haversine calculation. The output distance is in kilometers.

    References:
      * http://en.wikipedia.org/wiki/Haversine_formula
      * http://www.movable-type.co.uk/scripts/latlong.html
    """
    cdef double a, c, dLat, dLon

    dLat = deg2rad(lat2 - lat1) / 2.0
    dLon = deg2rad(lon2 - lon1) / 2.0

    lat1 = deg2rad(lat1)
    lat2 = deg2rad(lat2)

    a = pow(sin(dLat), 2) + cos(lat1) * cos(lat2) * pow(sin(dLon), 2)
    c = asin(fmin(1, sqrt(a)))
    return 2 * EARTH_RADIUS * c
