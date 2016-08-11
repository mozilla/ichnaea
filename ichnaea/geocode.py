"""
Contains a reverse geocoder to turn lat/lon and mcc data into region
codes.
"""

from collections import namedtuple
import os

import genc
import mobile_codes
from shapely import geometry
from shapely import prepared
import simplejson
from rtree import index

from ichnaea import geocalc
from ichnaea import util

REGIONS_FILE = os.path.join(os.path.abspath(
    os.path.dirname(__file__)), 'regions.geojson.gz')
REGIONS_BUFFER_FILE = os.path.join(os.path.abspath(
    os.path.dirname(__file__)), 'regions_buffer.geojson.gz')

DATELINE_EAST = geometry.box(180.0, -90.0, 270.0, 90.0)
DATELINE_WEST = geometry.box(-270.0, -90.0, -180.0, 90.0)

# Palestine only exists as West Bank/Gaza in the GENC dataset
MCC_TO_GENC_MAP = {
    'PS': 'XW',
}

Region = namedtuple('Region', 'code name radius')


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
    _radii = None  #: A cache of region radii

    def __init__(self,
                 regions_file=REGIONS_FILE,
                 buffer_file=REGIONS_BUFFER_FILE):
        self._buffered_shapes = {}
        self._prepared_shapes = {}
        self._shapes = {}
        self._tree_ids = {}
        self._radii = {}

        with util.gzip_open(regions_file, 'r') as fd:
            regions_data = simplejson.load(fd)

        genc_regions = frozenset([rec.alpha2 for rec in genc.REGIONS])
        for feature in regions_data['features']:
            code = feature['properties']['alpha2']
            if code in genc_regions:
                shape = geometry.shape(feature['geometry'])
                self._shapes[code] = shape
                self._prepared_shapes[code] = prepared.prep(shape)
                self._radii[code] = feature['properties']['radius']

        with util.gzip_open(buffer_file, 'r') as fd:
            buffer_data = simplejson.load(fd)

        i = 1
        envelopes = []
        for feature in buffer_data['features']:
            code = feature['properties']['alpha2']
            if code in genc_regions:
                shape = geometry.shape(feature['geometry'])
                self._buffered_shapes[code] = prepared.prep(shape)
                # Collect rtree index entries, and maintain a separate id to
                # code mapping. We don't use index object support as it
                # requires un/pickling the object entries on each lookup.
                if isinstance(shape, geometry.base.BaseMultipartGeometry):
                    # Index bounding box of individual polygons instead of
                    # the multipolygon, to avoid issues with regions crossing
                    # the -180.0/+180.0 longitude boundary.
                    for geom in shape.geoms:
                        envelopes.append((i, geom.envelope.bounds, None))
                        self._tree_ids[i] = code
                        i += 1
                else:
                    envelopes.append((i, shape.envelope.bounds, None))
                    self._tree_ids[i] = code
                    i += 1

        # Work around a bug in RTree:
        # https://github.com/Toblerity/rtree/issues/71
        # Insert a fake 0 entry at creation time, as streaming entries
        # is broken and results in envelope ids being set to 0.
        self._tree_ids[0] = None
        init_envelopes = [(0, (-180.0, -90.0, -180.0, -90.0), None)]

        props = index.Property()
        props.fill_factor = 0.9
        props.leaf_capacity = 20
        self._tree = index.Index(init_envelopes,
                                 interleaved=True, properties=props)
        for envelope in envelopes:
            self._tree.insert(*envelope)
        self._valid_regions = frozenset(self._shapes.keys())

    @property
    def valid_regions(self):
        return self._valid_regions

    def region(self, lat, lon):
        """
        Return a region code matching the provided position.
        If the position is not found inside any region return None.
        """
        # Look up point in RTree of buffered region envelopes.
        # This is a coarse-grained but very fast match.
        point = geometry.Point(lon, lat)
        codes = [self._tree_ids[id_] for id_ in
                 self._tree.intersection(point.bounds)
                 if self._tree_ids[id_]]

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
                coords = []
                if isinstance(self._shapes[code].boundary,
                              geometry.base.BaseMultipartGeometry):
                    for geom in self._shapes[code].boundary.geoms:
                        coords.extend([coord for coord in geom.coords])
                else:
                    coords = self._shapes[code].boundary.coords
                for coord in coords:
                    distances[geocalc.distance(
                        coord[1], coord[0], lat, lon)] = code
            return distances[min(distances.keys())]

        # point was in multiple overlapping regions, take the one where it
        # is farthest away from the border / the most inside a region
        for code in precise_codes:
            coords = []
            if isinstance(self._shapes[code].boundary,
                          geometry.base.BaseMultipartGeometry):
                for geom in self._shapes[code].boundary.geoms:
                    coords.extend([coord for coord in geom.coords])
            else:
                coords = self._shapes[code].boundary.coords
            for coord in coords:
                distances[geocalc.distance(
                    coord[1], coord[0], lat, lon)] = code
        return distances[max(distances.keys())]

    def any_region(self, lat, lon):
        """
        Is the provided lat/lon position inside any of the regions?

        Returns False if the position is outside of all known regions.
        """
        point = geometry.Point(lon, lat)
        codes = [self._tree_ids[id_] for id_ in
                 self._tree.intersection(point.bounds)
                 if self._tree_ids[id_]]

        for code in codes:
            if self._buffered_shapes[code].contains(point):
                return True

        return False

    def in_region(self, lat, lon, code):
        """
        Is the provided lat/lon position inside the region associated
        with the given region code.
        """
        if code not in self._valid_regions:
            return False

        point = geometry.Point(lon, lat)
        if self._buffered_shapes[code].contains(point):
            return True
        return False

    def in_region_mcc(self, lat, lon, mcc):
        """
        Is the provided lat/lon position inside one of the regions
        associated with the given mcc.
        """
        for code in self.regions_for_mcc(mcc):
            if self.in_region(lat, lon, code):
                return True
        return False

    def region_for_code(self, code):
        """
        Return a region instance with metadata for the code or None.

        The return list is filtered by the set of recognized
        region codes present in the GENC dataset.
        """
        if code in self._valid_regions:
            region = genc.region_by_alpha2(code)
            return Region(
                code=region.alpha2,
                name=region.name,
                radius=self.region_max_radius(code))
        return None

    def regions_for_mcc(self, mcc, metadata=False):
        """
        Return a list of region codes matching the passed in
        mobile country code.

        If the metadata argument is set to True, returns a list of
        region instances containing additional metadata instead.

        The return list is filtered by the set of recognized
        region codes present in the GENC dataset.
        """
        codes = [region.alpha2 for region in mobile_codes.mcc(str(mcc))]
        # map mcc region codes to genc region codes
        codes = [MCC_TO_GENC_MAP.get(code, code) for code in codes]
        valid_codes = set(codes).intersection(self._valid_regions)
        if not metadata:
            return list(valid_codes)

        result = []
        for code in valid_codes:
            region = genc.region_by_alpha2(code)
            if region is not None:
                result.append(Region(
                    code=region.alpha2,
                    name=region.name,
                    radius=self.region_max_radius(code)))
        return result

    def region_for_cell(self, lat, lon, mcc):
        """
        Return a region code matching the provided mcc and position.
        If the position is not found inside any region return None.
        """
        regions = []
        for code in self.regions_for_mcc(mcc):
            if self.in_region(lat, lon, code):
                regions.append(code)

        if not regions:
            return None
        if len(regions) == 1:
            return regions[0]

        # fall back to lookup without the mcc/region code hint
        return self.region(lat, lon)

    def region_max_radius(self, code):
        """
        Return the maximum radius of a circle encompassing the largest
        region subunit in meters, rounded to 1 km increments.
        """
        return self._radii.get(code, None)


GEOCODER = Geocoder()
