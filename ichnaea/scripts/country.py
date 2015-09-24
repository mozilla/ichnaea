from collections import defaultdict
import json
import os

import genc
import shapely
import shapely.geometry
import shapely.ops

REGION_CODES = set([reg.alpha2 for reg in genc.REGIONS])
# exclude Antarctica
REGION_CODES = REGION_CODES - set(['AQ'])
REGION_CODE_MAP = {
    'AX': 'FI',
    'BM': 'GB',
    'BV': 'NO',
    'GG': 'GB',
    'GU': 'US',
    'IM': 'GB',
    'JE': 'GB',
    'NF': 'AU',
    'PR': 'US',
    'PS': 'XW',
    'TC': 'GB',
    'YT': 'FR',
    'ATC': 'AU',
    'CYN': 'CY',
    'IOA': 'AU',
    'KOS': 'XK',
    'SOL': 'SO',
}
ISLANDS_REGION = [
    'AU, ''BM', 'BS', 'CA', 'CV', 'FJ', 'FM', 'GL', 'GR', 'GU',
    'ID', 'IS', 'JA', 'KI', 'MP', 'NC', 'NZ', 'PF, ''PH', 'SB',
    'TC', 'TO', 'TR', 'VU', 'WS',
]


def simplify(features):
    regions = defaultdict(list)
    for feature in features:
        code = feature['properties']['iso_a2']
        code = REGION_CODE_MAP.get(code, code)
        adm_code = feature['properties']['adm0_a3']
        if code not in REGION_CODES:
            if adm_code in REGION_CODE_MAP:
                code = REGION_CODE_MAP.get(adm_code)
            else:
                continue
        regions[code].append(shapely.geometry.shape(feature['geometry']))

    for code, shapes in regions.items():
        if len(shapes) == 1:
            shape = shapes[0]
        else:
            shape = shapely.ops.cascaded_union(shapes)
        if code in ISLANDS_REGION:
            buf = 0.8
        else:
            buf = 0.2
        factor = min(shape.area / 100, 0.03)
        regions[code] = shape.buffer(buf).buffer(-buf).simplify(factor)

    return regions


def to_geojson(regions):
    features = []
    for code, region in regions.items():
        features.append({
            'type': 'Feature',
            'properties': {
                'alpha2': code,
            },
            'geometry': shapely.geometry.mapping(region),
        })

    def _sort(value):
        return value['properties']['alpha2']

    features = sorted(features, key=_sort)
    lines = ',\n'.join([json.dumps(f, sort_keys=True, separators=(',', ':'))
                        for f in features])
    return '{"type": "FeatureCollection", "features": [\n' + lines + '\n]}\n'


def main():
    os.system('ogr2ogr -f GeoJSON '
              '-select "iso_a2, adm0_a3" -segmentize 0.1 '
              'data/temp.geojson data/ne_50m_admin_0_countries.dbf')
    with open('data/temp.geojson', 'r') as fd:
        jsondata = fd.read()
    os.remove('data/temp.geojson')
    data = json.loads(jsondata)
    simplified = simplify(data['features'])
    output = to_geojson(simplified)
    with open('ichnaea/countries.geojson', 'w') as fd:
        fd.write(output)

if __name__ == '__main__':
    main()
