"""
Contains helper functions for region related tasks.
"""

import os

from country_bounding_boxes import country_subunits_by_iso_code
import mobile_codes
from shapely import geometry
from shapely import prepared
import simplejson
from six import string_types
from rtree import index

from ichnaea.constants import ALL_VALID_COUNTRIES
from ichnaea import geocalc

JSON_FILE = os.path.join(os.path.abspath(
    os.path.dirname(__file__)), 'regions.geojson')

_RADIUS_CACHE = {}


class Geocoder(object):
    """
    The Geocoder offers reverse geocoding lat/lon positions
    into region codes.
    """

    _buffered_shapes = None  #: maps region code to a buffered prepared shape
    _prepared_shapes = None  #: maps region code to a precise prepared shape
    _shapes = None  #: maps region code to a precise shape
    _tree = None  #: RTree of buffered region envelopes
    _tree_ids = None  #: maps RTree entry id to region code

    def __init__(self, json_file=JSON_FILE):
        self.json_file = json_file
        self._buffered_shapes = {}
        self._prepared_shapes = {}
        self._shapes = {}
        self._tree_ids = {}

    def _fill_caches(self):
        with open(self.json_file, 'r') as fd:
            data = simplejson.load(fd)

        for feature in data['features']:
            code = feature['properties']['alpha2']
            self._shapes[code] = shape = geometry.shape(feature['geometry'])
            self._prepared_shapes[code] = prepared.prep(shape)

        envelopes = []
        for i, (code, shape) in enumerate(self._shapes.items()):
            # Build up region buffers, to create shapes that include all of
            # the coastal areas and boundaries of the regions and anywhere
            # a cell signal could still be recorded. The value is in decimal
            # degrees (1.0 == ~100km) but calculations don't take projection
            # / WSG84 into account.
            buffered = shape.buffer(0.5)
            # Collect rtree index entries, and maintain a separate id to
            # code mapping. We don't use index object support as it
            # requires un/pickling the object entries on each lookup.
            envelopes.append((i, buffered.envelope.bounds, None))
            self._tree_ids[i] = code
            self._buffered_shapes[code] = prepared.prep(buffered)

        props = index.Property()
        props.fill_factor = 0.9
        props.leaf_capacity = 20
        self._tree = index.Index(envelopes, interleaved=True, properties=props)

    def region(self, lat, lon):
        """
        Return a alpha2 region code matching the provided position.
        If the position is not found inside any region return None.
        """
        if self._tree is None:  # pragma: no cover
            self._fill_caches()

        # Look up point in RTree of buffered region envelopes.
        # This is a coarse-grained but very fast match.
        point = geometry.Point(lon, lat)
        codes = [self._tree_ids[id_] for id_ in
                 self._tree.intersection(point.bounds)]

        if len(codes) < 2:
            return codes[0] if codes else None

        # match point against the buffered polygon shapes
        buffered_codes = [code for code in codes
                          if self._buffered_shapes[code].contains(point)]
        if len(buffered_codes) < 2:
            return buffered_codes[0] if buffered_codes else None

        # match point against the precise polygon shapes
        precise_codes = [code for code in buffered_codes
                         if self._prepared_shapes[code].contains(point)]

        if len(precise_codes) == 1:
            return precise_codes[0]

        # Use distance from the border of each region as the tie-breaker.
        distances = {}

        # point wasn't in any precise region, which one of the buffered
        # regions is it closest to?
        if not precise_codes:
            for code in buffered_codes:
                distances[self._shapes[code].boundary.distance(point)] = code
            return distances[min(distances.keys())]

        # point was in multiple overlapping regions, take the one where it
        # is farthest away from the border / the most inside a region
        for code in precise_codes:
            distances[self._shapes[code].boundary.distance(point)] = code
        return distances[max(distances.keys())]

    def any_region(self, lat, lon):
        """
        Is the provided lat/lon position inside any of the regions?

        Returns False if the position is outside of all known regions.
        """
        if self._tree is None:  # pragma: no cover
            self._fill_caches()

        point = geometry.Point(lon, lat)
        codes = [self._tree_ids[id_] for id_ in
                 self._tree.intersection(point.bounds)]

        for code in codes:
            if self._buffered_shapes[code].contains(point):
                return True

        return False

    def in_region(self, lat, lon, code):
        """
        Is the provided lat/lon position inside the region associated
        with the given alpha2 region code.
        """
        if self._tree is None:  # pragma: no cover
            self._fill_caches()

        if code not in ALL_VALID_COUNTRIES:
            return False

        point = geometry.Point(lon, lat)
        if self._buffered_shapes[code].contains(point):
            return True
        return False


def regions_for_mcc(mcc):
    """
    Return a list of :class:`mobile_codes.Country` instances matching
    the passed in mobile country code.

    The return list is filtered by the set of recognized ISO 3166 alpha2
    codes present in the GENC dataset.
    """
    regions = mobile_codes.mcc(str(mcc))
    return [r for r in regions if r.alpha2 in ALL_VALID_COUNTRIES]


def region_max_radius(code):
    """
    Return the maximum radius of a circle encompassing the largest
    region subunit in meters, rounded to 1 km increments.
    """
    if not isinstance(code, string_types):
        return None
    code = code.upper()
    if len(code) not in (2, 3):
        return None

    value = _RADIUS_CACHE.get(code, None)
    if value:
        return value

    diagonals = []
    for country in country_subunits_by_iso_code(code):
        (lon1, lat1, lon2, lat2) = country.bbox
        diagonals.append(geocalc.distance(lat1, lon1, lat2, lon2))
    if diagonals:
        # Divide by two to get radius, round to 1 km and convert to meters
        radius = max(diagonals) / 2.0 / 1000.0
        value = _RADIUS_CACHE[code] = round(radius) * 1000.0

    return value

GEOCODER = Geocoder()
