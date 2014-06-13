import math
from country_bounding_boxes import country_subunits_by_iso_code

EARTH_RADIUS = 6371  # radius of earth in km


def distance(lat1, lon1, lat2, lon2):
    """
    Compute the distance between a pair of lat/longs in meters using
    the haversine calculation. The output distance is in kilometers.

    Error is up to 0.55%, which works out to 5m per 1km. This is
    still better than what GPS provides so it should be 'good enough'.

    Reference :
        http://en.wikipedia.org/wiki/Haversine_formula
        http://www.movable-type.co.uk/scripts/latlong.html

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
    dLon = math.radians(lon2 - lon1)
    dLat = math.radians(lat2 - lat1)

    lat1 = math.radians(lat1)
    lat2 = math.radians(lat2)

    a = math.sin(dLat / 2.0) * math.sin(dLat / 2.0) + \
        math.cos(lat1) * \
        math.cos(lat2) * \
        math.sin(dLon / 2.0) * \
        math.sin(dLon / 2.0)
    c = 2 * math.asin(min(1, math.sqrt(a)))
    d = EARTH_RADIUS * c
    return d


def centroid(points):
    """
    Compute the centroid (average lat and lon) from a set of points
    ((lat,lon) pairs).
    """
    lat_avg = sum([p[0] for p in points]) / len(points)
    lon_avg = sum([p[1] for p in points]) / len(points)
    return (lat_avg, lon_avg)


def range_to_points(point, points):
    """
    Compute the maximum distance, in km, from a (lat, lon) point to any
    of the points in a set of points ((lat,lon) pairs).

    """
    (p_lat, p_lon) = point
    return max([distance(p_lat, p_lon, p[0], p[1]) for p in points])


def location_is_in_country(lat, lon, country):
    """
    Return whether or not a given lat, lon pair is inside one of the
    country subunits associated with a given alpha2 country code.

    """
    assert isinstance(country, basestring)
    assert len(country) == 2
    assert isinstance(lat, float)
    assert isinstance(lon, float)
    for c in country_subunits_by_iso_code(country):
        (lon1, lat1, lon2, lat2) = c.bbox
        if lon1 <= lon and lon <= lon2 and \
           lat1 <= lat and lat <= lat2:
            return True
    return False
