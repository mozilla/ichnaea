from collections import defaultdict
import json
import os
import sys

import genc
import numpy
import shapely
import shapely.geometry
import shapely.ops

from ichnaea import geocalc
from ichnaea import util

DATELINE_EAST = shapely.geometry.box(180.0, -90.0, 270.0, 90.0)
DATELINE_WEST = shapely.geometry.box(-270.0, -90.0, -180.0, 90.0)

REGION_CODES = set([reg.alpha3 for reg in genc.REGIONS])
REGION_CODE_MAP = {
    'ALD': 'FI',
    'KOS': 'XK',
    'PSX': 'XW',
    'SAH': 'EH',
    'SJM': 'XR',
}
REGION_SETTINGS = {
    'AQ': (10.0, 0.1),
    'IL': (0.05, 0.0001),
    'XW': (0.05, 0.0001),
}
ISLANDS_REGION = [
    'AU', 'BM', 'BS', 'CA', 'CV', 'FJ', 'FM', 'GL', 'GR', 'GU',
    'ID', 'IS', 'JA', 'KI', 'MP', 'NC', 'NZ', 'PF, ''PH', 'SB',
    'TC', 'TO', 'TR', 'TV', 'VU', 'WS', 'XR',
]
EXTRA_REGIONS = {
    'GI': [{
        # Gibraltar
        "type": "Polygon",
        "coordinates": [[
            [-5.368, 36.1086], [-5.368, 36.155],
            [-5.336, 36.155], [-5.336, 36.1086],
            [-5.368, 36.1086],
        ]]
    }],
    'CO': [{
        # Archipelago of San Andres, Providencia and Santa Catalina
        "type": "Polygon",
        "coordinates": [[
            [-81.400452, 13.318469], [-81.400452, 13.400808],
            [-81.342087, 13.400808], [-81.342087, 13.318469],
            [-81.400452, 13.318469],
        ]]
    }, {
        "type": "Polygon",
        "coordinates": [[
            [-81.857757, 12.181649], [-81.857757, 12.604155],
            [-81.443023, 12.604155], [-81.443023, 12.181649],
            [-81.857757, 12.181649],
        ]]
    }, {
        "type": "Polygon",
        "coordinates": [[
            [-80.370483, 14.471915], [-80.370483, 14.471915],
            [-80.112305, 14.471915], [-80.112305, 14.269707],
            [-80.370483, 14.269707],
        ]]
    }, {
        "type": "Polygon",
        "coordinates": [[
            [-80.101318, 13.485789], [-80.101318, 13.571241],
            [-80.018921, 13.571241], [-80.018920, 13.485789],
            [-80.101318, 13.485789],
        ]]
    }, {
        "type": "Polygon",
        "coordinates": [[
            [-78.744507, 15.776395], [-78.744507, 15.908508],
            [-78.530273, 15.908508], [-78.530273, 15.776395],
            [-78.744507, 15.776395],
        ]]
    }, {
        "type": "Polygon",
        "coordinates": [[
            [-79.767608, 15.736745], [-79.767608, 15.859636],
            [-79.609681, 15.859636], [-79.609681, 15.736745],
            [-79.767608, 15.736745],
        ]]
    }, {
        "type": "Polygon",
        "coordinates": [[
            [-81.191711, 14.273699], [-81.191711, 14.342895],
            [-81.099701, 14.342895], [-81.099701, 14.273699],
            [-81.191711, 14.273699],
        ]]
    }],
    'IT': [{
        # Pelagie Islands, incl. Lampedusa
        "type": "Polygon",
        "coordinates": [[
            [12.444763, 35.497574], [12.314301, 35.551781],
            [12.849884, 35.883487], [12.907562, 35.885712],
            [12.646636, 35.486392], [12.444763, 35.497574],
        ]]
    }],
    'TV': [{
        # Tuvalu
        "type": "Polygon",
        "coordinates": [[
            [179.441071, -10.807003], [179.302368, -9.530332],
            [177.133941, -7.246684], [176.305847, -6.297554],
            [176.039085, -5.678509], [176.056595, -5.623844],
            [177.374267, -6.053161], [178.692627, -7.468688],
            [179.934082, -9.405711], [179.482269, -10.811724],
            [179.441071, -10.807003],
        ]]
    }],
    'CA': [{
        # fill in the inner lakes
        "type": "Polygon",
        "coordinates": [[
            [-128.05664, 70.495574], [-125.5957031, 72.073911],
            [-110.4785156, 78.716316], [-105.2050781, 79.269961],
            [-99.4921875, 80.178713], [-95.4492188, 80.703997],
            [-73.4765625, 69.411242], [-64.8632812, 61.606396],
            [-64.5117188, 57.610107], [-81.0351563, 51.289406],
            [-113.90625, 61.6063964], [-128.05664, 70.495574],
        ]]
    }],
}
PROPERTIES = ('iso_a3', 'adm0_a3', 'adm0_a3_is', 'adm0_a3_us')


def guess_code(props):
    code = None
    if props.get('adm0_a3_is') == 'SJM':
        return 'XR'

    for name in PROPERTIES:
        if props.get(name) in REGION_CODE_MAP:
            code = REGION_CODE_MAP.get(props[name])
            break
        elif props.get(name) in REGION_CODES:
            code = genc.region_by_alpha3(props[name]).alpha2
            break
    return code


def simplify(features):  # pragma: no cover
    regions = defaultdict(list)
    for feature in features:
        code = guess_code(feature['properties'])
        if not code:
            continue
        regions[code].append(shapely.geometry.shape(feature['geometry']))

    for code, polygons in EXTRA_REGIONS.items():
        for polygon in polygons:
            regions[code].append(shapely.geometry.shape(polygon))

    for code, shapes in regions.items():
        if len(shapes) == 1:
            shape = shapes[0]
        else:
            shape = shapely.ops.cascaded_union(shapes)

        buf, factor = REGION_SETTINGS.get(
            code, (0.2, min(shape.area / 100, 0.03)))

        if code in ISLANDS_REGION:
            buf = 0.8

        # actually simplify
        shape = shape.buffer(buf).buffer(-buf).simplify(factor)
        # remove anything crossing the -180.0/+180.0 longitude boundary
        shape = shape.difference(DATELINE_EAST).difference(DATELINE_WEST)
        regions[code] = shape

    return regions


def to_geojson(regions):  # pragma: no cover
    features = []
    for code, region in regions.items():
        # calculate the maximum radius of each polygon
        boundary = region.boundary
        if isinstance(boundary, shapely.geometry.base.BaseMultipartGeometry):
            boundaries = list(boundary.geoms)
        else:
            boundaries = [boundary]

        radii = []
        for boundary in boundaries:
            # flip x/y aka lon/lat to lat/lon
            boundary = numpy.fliplr(numpy.array(boundary))
            ctr_lat, ctr_lon = geocalc.centroid(boundary)
            radii.append(geocalc.max_distance(ctr_lat, ctr_lon, boundary))
        radius = round(max(radii) / 1000.0) * 1000.0

        features.append({
            'type': 'Feature',
            'properties': {
                'alpha2': code,
                'radius': radius,
            },
            'geometry': shapely.geometry.mapping(region),
        })

    def _sort(value):
        return value['properties']['alpha2']

    features = sorted(features, key=_sort)
    lines = ',\n'.join([json.dumps(f, sort_keys=True, separators=(',', ':'))
                        for f in features])
    return '{"type": "FeatureCollection", "features": [\n' + lines + '\n]}\n'


def main(argv):  # pragma: no cover
    os.system('ogr2ogr -f GeoJSON '
              '-select "%s" -segmentize 0.1 data/temp.geojson '
              'data/ne_50m_admin_0_map_subunits.dbf' % ', '.join(PROPERTIES))
    with open('data/temp.geojson', 'r') as fd:
        jsondata = fd.read()
    os.remove('data/temp.geojson')
    data = json.loads(jsondata)
    simplified = simplify(data['features'])
    output = to_geojson(simplified)
    with util.gzip_open('ichnaea/regions.geojson.gz',
                        'w', compresslevel=7) as fd:
        fd.write(output)


def console_entry():  # pragma: no cover
    main(sys.argv)
