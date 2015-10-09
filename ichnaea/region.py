"""
Contains helper functions for region related tasks.
"""

import os

from country_bounding_boxes import country_subunits_by_iso_code
import genc
import mobile_codes
from shapely import geometry
from shapely import prepared
import simplejson
from six import string_types
from rtree import index

from ichnaea import geocalc

JSON_FILE = os.path.join(os.path.abspath(
    os.path.dirname(__file__)), 'regions.geojson')

DATELINE_EAST = geometry.box(180.0, -90.0, 270.0, 90.0)
DATELINE_WEST = geometry.box(-270.0, -90.0, -180.0, 90.0)

# Palestine only exists as West Bank/Gaza in the GENC dataset
MCC_GENC_SHAPEFILE_MAP = {
    'PS': 'XW',
}
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
    _valid_regions = None  #: Set of known and valid region codes

    def __init__(self, json_file=JSON_FILE):
        self._buffered_shapes = {}
        self._prepared_shapes = {}
        self._shapes = {}
        self._tree_ids = {}

        with open(json_file, 'r') as fd:
            data = simplejson.load(fd)

        for feature in data['features']:
            code = feature['properties']['alpha2']
            self._shapes[code] = shape = geometry.shape(feature['geometry'])
            self._prepared_shapes[code] = prepared.prep(shape)

        i = 0
        envelopes = []
        for code, shape in self._shapes.items():
            # Build up region buffers, to create shapes that include all of
            # the coastal areas and boundaries of the regions and anywhere
            # a cell signal could still be recorded. The value is in decimal
            # degrees (1.0 == ~100km) but calculations don't take projection
            # / WSG84 into account.
            # After buffering remove any parts that crosses the -180.0/+180.0
            # longitude boundary to the east or west.
            buffered = (shape.buffer(0.5)
                             .difference(DATELINE_EAST)
                             .difference(DATELINE_WEST))
            self._buffered_shapes[code] = prepared.prep(buffered)

            # Collect rtree index entries, and maintain a separate id to
            # code mapping. We don't use index object support as it
            # requires un/pickling the object entries on each lookup.
            if isinstance(buffered, geometry.base.BaseMultipartGeometry):
                # Index bounding box of individual polygons instead of
                # the multipolygon, to avoid issues with regions crossing
                # the -180.0/+180.0 longitude boundary.
                for geom in buffered.geoms:
                    envelopes.append((i, geom.envelope.bounds, None))
                    self._tree_ids[i] = code
                    i += 1
            else:
                envelopes.append((i, buffered.envelope.bounds, None))
                self._tree_ids[i] = code
                i += 1

        props = index.Property()
        props.fill_factor = 0.9
        props.leaf_capacity = 20
        self._tree = index.Index(envelopes, interleaved=True, properties=props)

        regions = set(self._shapes.keys())
        genc_regions = set([rec.alpha2 for rec in genc.REGIONS])
        self._valid_regions = frozenset(genc_regions.intersection(regions))

    @property
    def valid_regions(self):
        return self._valid_regions

    def region(self, lat, lon):
        """
        Return a alpha2 region code matching the provided position.
        If the position is not found inside any region return None.
        """
        # Look up point in RTree of buffered region envelopes.
        # This is a coarse-grained but very fast match.
        point = geometry.Point(lon, lat)
        codes = [self._tree_ids[id_] for id_ in
                 self._tree.intersection(point.bounds)]

        if not codes:
            return None

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
        point = geometry.Point(lon, lat)
        codes = [self._tree_ids[id_] for id_ in
                 self._tree.intersection(point.bounds)]

        for code in codes:
            if self._buffered_shapes[code].contains(point):
                return True

        return False

    def in_region(self, lat, lon, alpha2):
        """
        Is the provided lat/lon position inside the region associated
        with the given alpha2 region code.
        """
        if alpha2 not in self._valid_regions:
            return False

        point = geometry.Point(lon, lat)
        if self._buffered_shapes[alpha2].contains(point):
            return True
        return False

    def in_region_mcc(self, lat, lon, mcc):
        """
        Is the provided lat/lon position inside one of the regions
        associated with the given mcc.
        """
        for alpha2 in self.regions_for_mcc(mcc):
            if self.in_region(lat, lon, alpha2):
                return True
        return False

    def regions_for_mcc(self, mcc, names=False):
        """
        Return a list of alpha2 region codes matching the passed in
        mobile country code.

        If the names argument is set to True, returns a list of
        :class:`genc.regions.Region` instances instead.

        The return list is filtered by the set of recognized alpha2
        region codes present in the GENC dataset and those that we have
        region shapefiles for.
        """
        codes = [region.alpha2 for region in mobile_codes.mcc(str(mcc))]
        # map mcc alpha2 codes to genc alpha2 codes
        codes = [MCC_GENC_SHAPEFILE_MAP.get(code, code) for code in codes]
        valid_codes = set(codes).intersection(self._valid_regions)
        if not names:
            return list(valid_codes)

        result = []
        for alpha2 in valid_codes:
            region = genc.region_by_alpha2(alpha2)
            if region is not None:
                result.append(region)
        return result

    def region_for_cell(self, lat, lon, mcc):
        """
        Return a alpha2 region code matching the provided mcc and position.
        If the position is not found inside any region return None.
        """
        regions = []
        for alpha2 in self.regions_for_mcc(mcc):
            if self.in_region(lat, lon, alpha2):
                regions.append(alpha2)

        if not regions:
            return None
        if len(regions) == 1:
            return regions[0]

        # fall back to lookup without the mcc/alpha2 hint
        return self.region(lat, lon)


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
    for region in country_subunits_by_iso_code(code):
        (lon1, lat1, lon2, lat2) = region.bbox
        diagonals.append(geocalc.distance(lat1, lon1, lat2, lon2))
    if diagonals:
        # Divide by two to get radius, round to 1 km and convert to meters
        radius = max(diagonals) / 2.0 / 1000.0
        value = _RADIUS_CACHE[code] = round(radius) * 1000.0

    return value

GEOCODER = Geocoder()
