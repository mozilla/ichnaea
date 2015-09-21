"""
Contains helper functions for various geo related calculations.
"""

from operator import attrgetter
from collections import namedtuple

from country_bounding_boxes import (
    _best_guess_iso_2,
    _best_guess_iso_3,
    countries,
    country_subunits_by_iso_code,
)
import numpy
from six import string_types

from ichnaea import _geocalc

_bbox_cache = []
_radius_cache = {}
Subunit = namedtuple('Subunit', 'bbox alpha2 alpha3 radius')


def _fill_bbox_cache():
    cached = []
    for country in countries:
        iso2 = _best_guess_iso_2(country)
        iso3 = _best_guess_iso_3(country)
        if not (iso2 and iso3):
            continue
        (lon1, lat1, lon2, lat2) = country.bbox
        radius = _geocalc.distance(lat1, lon1, lat2, lon2) / 2.0
        cached.append(Subunit(bbox=country.bbox,
                              alpha2=iso2.upper(),
                              alpha3=iso3.upper(),
                              radius=radius))
    # sort by largest radius first
    return list(sorted(cached, key=attrgetter('radius'), reverse=True))


def aggregate_position(circles, minimum_accuracy):
    """
    Calculate the aggregate position based on a number of circles
    (numpy 3-column arrays of lat/lon/radius).

    Return the position and an accuracy estimate, but at least
    use the minimum_accuracy.
    """
    if len(circles) == 1:
        return (float(circles[0][0]),
                float(circles[0][1]),
                max(float(circles[0][2]), minimum_accuracy))

    points, _ = numpy.hsplit(circles, [2])
    lat, lon = _geocalc.centroid(points)

    # Bad approximation. This one takes the maximum distance from
    # the centroid to any of the provided circle centers.
    # It ignores the radius of those circles.
    radius = _geocalc.max_distance(lat, lon, points)
    return (lat, lon, max(radius, minimum_accuracy))


def circle_radius(lat, lon, max_lat, max_lon, min_lat, min_lon):
    """
    Compute the maximum distance, in meters, from a (lat, lon) point
    to any of the extreme points of a bounding box.
    """
    points = numpy.array([
        (min_lat, min_lon),
        (min_lat, max_lon),
        (max_lat, min_lon),
        (max_lat, max_lon),
    ], dtype=numpy.double)

    radius = _geocalc.max_distance(lat, lon, points)
    return int(round(radius))


def country_for_location(lat, lon):
    """
    Return a ISO alpha2 country code matching the provided location.
    If the location is found inside multiple or no countries return None.
    """
    res = set()
    for subunit in _bbox_cache:
        (lon1, lat1, lon2, lat2) = subunit.bbox
        if (lon1 <= lon <= lon2) and (lat1 <= lat <= lat2):
            res.add(subunit.alpha2)
            if len(res) > 1:
                return None

    if len(res) == 1:
        return list(res)[0]
    return None


def country_matches_location(lat, lon, country_code, margin=0.0):
    """
    Return whether or not a given (lat, lon) pair is inside one of the
    country subunits associated with a given alpha2 country code.
    """
    for country in country_subunits_by_iso_code(country_code):
        (lon1, lat1, lon2, lat2) = country.bbox
        if lon1 - margin <= lon and lon <= lon2 + margin and \
           lat1 - margin <= lat and lat <= lat2 + margin:
            return True
    return False


def country_max_radius(country_code):
    """
    Return the maximum radius of a circle encompassing the largest
    country subunit in meters, rounded to 1 km increments.
    """
    if not isinstance(country_code, string_types):
        return None
    country_code = country_code.upper()
    if len(country_code) not in (2, 3):
        return None

    value = _radius_cache.get(country_code, None)
    if value:
        return value

    diagonals = []
    for country in country_subunits_by_iso_code(country_code):
        (lon1, lat1, lon2, lat2) = country.bbox
        diagonals.append(_geocalc.distance(lat1, lon1, lat2, lon2))
    if diagonals:
        # Divide by two to get radius, round to 1 km and convert to meters
        radius = max(diagonals) / 2.0 / 1000.0
        value = _radius_cache[country_code] = round(radius) * 1000.0

    return value

# fill the bbox cache
_bbox_cache = _fill_bbox_cache()
