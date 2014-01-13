import math

EARTH_RADIUS = 6371 # radius of earth in km

def distance(lat1, lon1, lat2, lon2):
    """
    Compute the distance between a pair of lat/longs in meters using
    haversine.  The output distance is in kilometers.

    http://gis.stackexchange.com/questions/4906/why-is-law-of-cosines-more-preferable-than-haversine-when-calculating-distance-b

    and 

    http://www.movable-type.co.uk/scripts/latlong.html

    are useful resources for this.
    """
    dLon = math.radians(lon2-lon1)
    dLat = math.radians(lat2-lat1)

    lat1 = math.radians(lat1)
    lat2 = math.radians(lat2)

    a = math.sin(dLat/2.0) * math.sin(dLat/2.0) + \
        math.cos(lat1) * \
        math.cos(lat2) * \
        math.sin(dLon/2.0) * \
        math.sin(dLon/2.0)
    c = 2 * math.asin(min(1, math.sqrt(a)))
    d = EARTH_RADIUS * c
    return d

