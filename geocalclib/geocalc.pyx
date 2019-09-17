# cython: language_level=3, emit_code_comments=False

from libc.math cimport asin, atan, atan2, cos
from libc.math cimport fmax, fmin, M_PI, sin, sqrt, tan
from numpy cimport double_t, ndarray
cimport cython

import numpy

cdef double MAX_LAT = 85.051  # Max Web Mercator latitude
cdef double MIN_LAT = -85.051  # Min Web Mercator latitude
cdef double MAX_LON = 180.0  # Max Web Mercator longitude
cdef double MIN_LON = -180.0  # Min Web Mercator longitude

# Constant used in Haversine formula, Earth radius in km.
cdef double EARTH_RADIUS = 6371.009

# Constants for WSG-84 ellipsoid
cdef double EARTH_MAJOR_RADIUS = 6378.137
cdef double EARTH_MINOR_RADIUS = 6356.752314245
cdef double EARTH_FLATTENING = 0.0033528106647474805  # 1.0 / 298.257223563
cdef double VINCENTY_CUTOFF = 0.00000000001  # 10e-12
cdef int VINCENTY_ITERATIONS = 25

cdef double* RANDOM_LAT = [
    0.8218, 0.1382, 0.8746, 0.0961, 0.8159, 0.2876, 0.6191, 0.0897,
    0.3755, 0.9412, 0.3231, 0.5353, 0.225, 0.0555, 0.1591, 0.3871,
    0.8714, 0.2496, 0.7499, 0.0279, 0.3794, 0.8224, 0.1459, 0.5992,
    0.3004, 0.5599, 0.8807, 0.1546, 0.7401, 0.834, 0.7581, 0.2057,
    0.4496, 0.1683, 0.3266, 0.1515, 0.9731, 0.4078, 0.9517, 0.6511,
    0.9287, 0.8405, 0.4579, 0.9462, 0.2645, 0.7315, 0.458, 0.3744,
    0.4637, 0.3643, 0.5599, 0.815, 0.8971, 0.6997, 0.1595, 0.0066,
    0.8548, 0.6805, 0.9786, 0.8293, 0.0041, 0.5027, 0.6556, 0.0273,
    0.0949, 0.6407, 0.0867, 0.2891, 0.9741, 0.2599, 0.3148, 0.8786,
    0.6432, 0.2424, 0.195, 0.4672, 0.3097, 0.0697, 0.493, 0.5484,
    0.7611, 0.2611, 0.6947, 0.632, 0.466, 0.1275, 0.4001, 0.7947,
    0.8693, 0.8536, 0.686, 0.9742, 0.8517, 0.6809, 0.0395, 0.7739,
    0.4133, 0.5117, 0.9562, 0.7003, 0.261, 0.9772, 0.1694, 0.2982,
    0.3459, 0.3611, 0.7994, 0.6209, 0.2771, 0.8388, 0.9764, 0.698,
    0.1615, 0.3205, 0.0766, 0.0832, 0.3695, 0.4471, 0.8077, 0.4343,
    0.716, 0.6502, 0.351, 0.1502, 0.9186, 0.3677, 0.8139, 0.6609,
    0.2635, 0.1418, 0.4809, 0.15, 0.1809, 0.1874, 0.0272, 0.6513,
    0.6073, 0.5867, 0.8034, 0.744, 0.3532, 0.2124, 0.2574, 0.0536,
    0.2066, 0.4326, 0.4771, 0.5265, 0.1183, 0.0778, 0.7552, 0.9647,
    0.4392, 0.3256, 0.4935, 0.8999, 0.1643, 0.4203, 0.8042, 0.8463,
    0.1369, 0.0638, 0.7694, 0.9243, 0.3213, 0.1072, 0.8301, 0.4133,
    0.731, 0.5625, 0.3609, 0.1266, 0.8004, 0.5228, 0.5915, 0.533,
    0.8568, 0.9744, 0.1226, 0.2214, 0.8163, 0.3973, 0.0492, 0.0257,
    0.4362, 0.6687, 0.7528, 0.1546, 0.8486, 0.1903, 0.3155, 0.4483,
    0.2951, 0.625, 0.1373, 0.3942, 0.7765, 0.1284, 0.3895, 0.0197,
]

cdef double* RANDOM_LON = [
    0.3366, 0.9381, 0.9013, 0.7668, 0.4397, 0.0931, 0.4599, 0.7187,
    0.2778, 0.9749, 0.8002, 0.867, 0.6856, 0.5892, 0.0715, 0.1547,
    0.6151, 0.8931, 0.0535, 0.0219, 0.669, 0.7393, 0.3453, 0.2699,
    0.2595, 0.3468, 0.5989, 0.5349, 0.6499, 0.973, 0.1924, 0.6981,
    0.0049, 0.7285, 0.2222, 0.907, 0.2086, 0.6255, 0.438, 0.7481,
    0.3976, 0.8766, 0.0788, 0.072, 0.4321, 0.7367, 0.5851, 0.7282,
    0.4919, 0.7602, 0.8871, 0.6833, 0.7713, 0.7626, 0.1701, 0.2766,
    0.7929, 0.9612, 0.5676, 0.0297, 0.1039, 0.1106, 0.3217, 0.7889,
    0.9967, 0.4868, 0.1648, 0.9118, 0.5572, 0.2365, 0.2466, 0.4317,
    0.2269, 0.107, 0.359, 0.8855, 0.8001, 0.6695, 0.659, 0.9648,
    0.3251, 0.7101, 0.5131, 0.693, 0.7862, 0.5623, 0.3496, 0.3707,
    0.4111, 0.5193, 0.4851, 0.5421, 0.7793, 0.163, 0.4101, 0.5883,
    0.7102, 0.7474, 0.1109, 0.4315, 0.2044, 0.0695, 0.9451, 0.8879,
    0.349, 0.7498, 0.7603, 0.2392, 0.6879, 0.8437, 0.8868, 0.5658,
    0.2767, 0.6489, 0.1796, 0.3364, 0.7185, 0.966, 0.4197, 0.0102,
    0.8892, 0.2361, 0.9872, 0.5313, 0.9641, 0.8675, 0.8401, 0.253,
    0.8521, 0.3932, 0.9406, 0.1951, 0.2688, 0.5872, 0.0671, 0.5138,
    0.4509, 0.0914, 0.8911, 0.2342, 0.2115, 0.4977, 0.0297, 0.3052,
    0.5143, 0.5642, 0.0268, 0.8893, 0.9661, 0.0796, 0.5527, 0.8903,
    0.3143, 0.7346, 0.0573, 0.3421, 0.4941, 0.4112, 0.6782, 0.8287,
    0.5729, 0.6492, 0.2224, 0.8022, 0.9722, 0.5225, 0.5149, 0.092,
    0.4232, 0.6636, 0.7266, 0.5325, 0.4495, 0.8719, 0.9192, 0.2562,
    0.327, 0.3825, 0.1051, 0.4907, 0.167, 0.9088, 0.3463, 0.511,
    0.0884, 0.071, 0.1059, 0.0939, 0.5202, 0.6005, 0.9173, 0.5957,
    0.8279, 0.7611, 0.8101, 0.9157, 0.004, 0.9844, 0.3872, 0.7046,
]

cdef inline double deg2rad(double degrees):
    return degrees * M_PI / 180.0


@cython.cdivision(True)
cdef inline double rad2deg(double radians):
    return radians * 180.0 / M_PI


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


cpdef double distance(double lat1, double lon1,
                      double lat2, double lon2):
    # Default to Vincenty distance, falling back to Haversine if
    # Vincenty doesn't converge in VINCENTY_ITERATIONS iterations.
    try:
        return vincenty_distance(lat1, lon1, lat2, lon2)
    except ValueError:
        return haversine_distance(lat1, lon1, lat2, lon2)


cpdef double haversine_distance(double lat1, double lon1,
                                double lat2, double lon2):
    """
    Compute the distance between a pair of lat/longs in meters using
    the Haversine calculation. The output distance is in meters.

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
    direction of travel.
    """
    cdef double a, c, dLat, dLon

    dLat = deg2rad(lat2 - lat1) / 2.0
    dLon = deg2rad(lon2 - lon1) / 2.0

    lat1 = deg2rad(lat1)
    lat2 = deg2rad(lat2)

    a = sin(dLat) ** 2 + cos(lat1) * cos(lat2) * sin(dLon) ** 2
    c = asin(fmin(1, sqrt(a)))
    return 1000.0 * 2.0 * EARTH_RADIUS * c


cpdef double vincenty_distance(double lat1, double lon1,
                               double lat2, double lon2) except -1:
    """
    Compute the distance between a pair of lat/longs in meters using
    the Vincenty formula.

    References:
      * https://en.wikipedia.org/wiki/Vincenty's_formulae
      * http://www.movable-type.co.uk/scripts/latlong-vincenty.html
      * https://github.com/geopy/geopy/blob/master/geopy/distance.py
    """
    cdef double delta_lon, reduced_lat1, reduced_lat2
    cdef double sin_reduced1, cos_reduced1, sin_reduced2, cos_reduced2
    cdef double lambda_lon, lambda_prime
    cdef double sin_lambda_lon, cos_lambda_lon, sin_sigma, cos_sigma
    cdef double sigma, sin_alpha, cos_sq_alpha, cos2_sigma_m
    cdef double u_sq, A, B, C, delta_sigma
    cdef int i

    lat1 = deg2rad(lat1)
    lon1 = deg2rad(lon1)
    lat2 = deg2rad(lat2)
    lon2 = deg2rad(lon2)

    delta_lon = lon2 - lon1

    reduced_lat1 = atan((1.0 - EARTH_FLATTENING) * tan(lat1))
    reduced_lat2 = atan((1.0 - EARTH_FLATTENING) * tan(lat2))

    sin_reduced1 = sin(reduced_lat1)
    cos_reduced1 = cos(reduced_lat1)
    sin_reduced2 = sin(reduced_lat2)
    cos_reduced2 = cos(reduced_lat2)

    lambda_lon = delta_lon
    lambda_prime = 2.0 * M_PI

    i = 0
    while (abs(lambda_lon - lambda_prime) > VINCENTY_CUTOFF and
           i <= VINCENTY_ITERATIONS):
        i += 1

        sin_lambda_lon = sin(lambda_lon)
        cos_lambda_lon = cos(lambda_lon)

        sin_sigma = sqrt(
            (cos_reduced2 * sin_lambda_lon) ** 2 +
            (cos_reduced1 * sin_reduced2 -
             sin_reduced1 * cos_reduced2 * cos_lambda_lon) ** 2
        )

        if sin_sigma == 0:
            return 0.0  # Coincident points

        cos_sigma = (
            sin_reduced1 * sin_reduced2 +
            cos_reduced1 * cos_reduced2 * cos_lambda_lon
        )

        sigma = atan2(sin_sigma, cos_sigma)

        sin_alpha = (
            cos_reduced1 * cos_reduced2 * sin_lambda_lon / sin_sigma
        )
        cos_sq_alpha = 1.0 - sin_alpha ** 2

        if cos_sq_alpha != 0.0:
            cos2_sigma_m = (
                cos_sigma - (2.0 * sin_reduced1 * sin_reduced2 / cos_sq_alpha)
            )
        else:
            cos2_sigma_m = 0.0  # Equatorial line

        C = (
            EARTH_FLATTENING / 16.0 * cos_sq_alpha *
            (4.0 + EARTH_FLATTENING * (4.0 - 3.0 * cos_sq_alpha))
        )

        lambda_prime = lambda_lon
        lambda_lon = (
            delta_lon + (1.0 - C) * EARTH_FLATTENING * sin_alpha *
                (sigma + C * sin_sigma *
                    (cos2_sigma_m + C * cos_sigma *
                        (-1.0 + 2.0 * cos2_sigma_m ** 2)))
        )

    if i > VINCENTY_ITERATIONS:
        raise ValueError("Vincenty formula failed to converge!")

    u_sq = (
        cos_sq_alpha *
        (EARTH_MAJOR_RADIUS ** 2 - EARTH_MINOR_RADIUS ** 2) /
        EARTH_MINOR_RADIUS ** 2
    )

    A = (
        1.0 + u_sq / 16384.0 *
        (4096.0 + u_sq *
            (-768.0 + u_sq * (320.0 - 175.0 * u_sq)))
    )

    B = (
        u_sq / 1024.0 *
        (256.0 + u_sq *
            (-128.0 + u_sq * (74.0 - 47.0 * u_sq)))
    )

    delta_sigma = (
        B * sin_sigma *
            (cos2_sigma_m + B / 4.0 *
                (cos_sigma *
                    (-1.0 + 2.0 * cos2_sigma_m ** 2) -
                    B / 6.0 * cos2_sigma_m *
                        (-3.0 + 4.0 * sin_sigma ** 2) *
                        (-3.0 + 4.0 * cos2_sigma_m ** 2)))
    )

    return 1000.0 * EARTH_MINOR_RADIUS * A * (sigma - delta_sigma)


cpdef tuple destination(double lat1, double lon1,
                        double bearing, double distance):
    """
    Given an initial point, a bearing and a distance in meters,
    compute the destination point using the Vincenty formula.

    References:
      * https://en.wikipedia.org/wiki/Vincenty's_formulae
      * http://www.movable-type.co.uk/scripts/latlong-vincenty.html
      * https://github.com/geopy/geopy/blob/master/geopy/distance.py
    """
    cdef int i
    cdef double tan_reduced1, cos_reduced1, sin_bearing, cos_bearing
    cdef double sigma1, sin_alpha, cos_sq_alpha, u_sq, A, B, C
    cdef double sigma, sigma_prime, cos2_sigma_m, sin_sigma, cos_sigma
    cdef double delta_sigma, lat2, lon2, lambda_lon, delta_lon

    lat1 = deg2rad(lat1)
    lon1 = deg2rad(lon1)
    bearing = deg2rad(bearing)
    distance = distance / 1000.0

    tan_reduced1 = (1.0 - EARTH_FLATTENING) * tan(lat1)
    cos_reduced1 = 1.0 / sqrt(1.0 + tan_reduced1 ** 2)
    sin_reduced1 = tan_reduced1 * cos_reduced1

    sin_bearing = sin(bearing)
    cos_bearing = cos(bearing)

    sigma1 = atan2(tan_reduced1, cos_bearing)
    sin_alpha = cos_reduced1 * sin_bearing
    cos_sq_alpha = 1.0 - sin_alpha ** 2

    u_sq = (
        cos_sq_alpha *
        (EARTH_MAJOR_RADIUS ** 2 - EARTH_MINOR_RADIUS ** 2) /
        EARTH_MINOR_RADIUS ** 2
    )

    A = 1.0 + u_sq / 16384.0 * (
        4096.0 + u_sq *
            (-768.0 + u_sq * (320.0 - 175.0 * u_sq))
    )

    B = u_sq / 1024.0 * (
        256.0 + u_sq *
            (-128.0 + u_sq * (74.0 - 47.0 * u_sq))
    )

    sigma = distance / (EARTH_MINOR_RADIUS * A)
    sigma_prime = 2 * M_PI

    i = 0
    while (abs(sigma - sigma_prime) > VINCENTY_CUTOFF and
           i <= VINCENTY_ITERATIONS):
        i += 1

        cos2_sigma_m = cos(2.0 * sigma1 + sigma)
        sin_sigma = sin(sigma)
        cos_sigma = cos(sigma)

        delta_sigma = (
            B * sin_sigma *
            (cos2_sigma_m + B / 4.0 *
                (cos_sigma *
                    (-1.0 + 2.0 * cos2_sigma_m ** 2) -
                    B / 6.0 * cos2_sigma_m *
                        (-3.0 + 4.0 * sin_sigma ** 2) *
                        (-3.0 + 4.0 * cos2_sigma_m ** 2)))
        )

        sigma_prime = sigma
        sigma = distance / (EARTH_MINOR_RADIUS * A) + delta_sigma

    if i > VINCENTY_ITERATIONS:
        raise ValueError("Vincenty formula failed to converge!")

    sin_sigma = sin(sigma)
    cos_sigma = cos(sigma)

    lat2 = atan2(
        sin_reduced1 * cos_sigma + cos_reduced1 * sin_sigma * cos_bearing,
        (1.0 - EARTH_FLATTENING) * sqrt(
            sin_alpha ** 2 +
            (sin_reduced1 * sin_sigma -
             cos_reduced1 * cos_sigma * cos_bearing) ** 2
        )
    )

    lambda_lon = atan2(
        sin_sigma * sin_bearing,
        cos_reduced1 * cos_sigma - sin_reduced1 * sin_sigma * cos_bearing
    )

    C = (
        EARTH_FLATTENING / 16.0 * cos_sq_alpha *
        (4.0 + EARTH_FLATTENING * (4.0 - 3.0 * cos_sq_alpha))
    )

    delta_lon = (
        lambda_lon - (1.0 - C) * EARTH_FLATTENING * sin_alpha *
            (sigma + C * sin_sigma *
                (cos2_sigma_m + C * cos_sigma *
                    (-1.0 + 2.0 * cos2_sigma_m ** 2)))
    )

    lon2 = lon1 + delta_lon
    lat2 = rad2deg(lat2)
    lon2 = rad2deg(lon2)

    return (lat2, lon2)


cpdef double latitude_add(double lat, double lon, double distance):
    """
    Return a latitude in degrees which is shifted by
    distance in meters.

    The new latitude is bounded by our globally defined
    :data:`ichnaea.constants.MIN_LAT` and
    :data:`ichnaea.constants.MAX_LAT`.
    """
    cdef double lat1, lon1

    lat1, lon1 = destination(lat, lon, 0.0, distance)

    return fmax(MIN_LAT, fmin(lat1, MAX_LAT))


cpdef double longitude_add(double lat, double lon, double distance):
    """
    Return a longitude in degrees which is shifted by
    distance in meters.

    The new longitude is bounded by our globally defined
    :data:`ichnaea.constants.MIN_LON` and
    :data:`ichnaea.constants.MAX_LON`.
    """
    cdef double lat1, lon1

    lat1, lon1 = destination(lat, lon, 90.0, distance)

    return fmax(MIN_LON, fmin(lon1, MAX_LON))


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


cpdef list random_points(long lat, long lon, int num):
    """
    Given a row from the datamap table, return a list of
    pseudo-randomized but stable points for the datamap grid.

    The points look random, but their position only depends on the
    passed in latitude and longitude. This ensures that on consecutive
    calls with the same input data, the exact same output data is
    returned, and the generated image tiles showing these points don't
    change. The randomness needs to be good enough to not show clear
    visual patterns for adjacent grid cells, so a change in one of
    the input arguments by 1 needs to result in a large change in
    the pattern.
    """
    cdef str pattern = '%.6f,%.6f\n'
    cdef list result = []
    cdef int i, lat_random, lon_random, multiplier
    cdef double lat_d, lon_d

    lat_d = float(lat)
    lon_d = float(lon)
    lat_random = int((lon * (lat * 17) % 1021) % 179)
    lon_random = int((lat * (lon * 11) % 1913) % 181)

    multiplier = min(max(13 - num, 0), 13) // 2

    for i in range(multiplier):
        result.append(pattern % (
            (lat_d + RANDOM_LAT[lat_random + i]) / 1000.0,
            (lon_d + RANDOM_LON[lon_random + i]) / 1000.0))

    return result
