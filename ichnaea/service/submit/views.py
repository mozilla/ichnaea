from pyramid.httpexceptions import HTTPNoContent

from ichnaea.decimaljson import dumps
from ichnaea.service.error import (
    preprocess_request,
)
from ichnaea.service.submit.schema import SubmitSchema
from ichnaea.service.submit.tasks import insert_measures
from ichnaea.service.base import check_api_key
from country_bounding_boxes import country_subunits_by_iso_code
from ichnaea.heka_logging import get_heka_client


def configure_submit(config):
    config.add_route('v1_submit', '/v1/submit')
    config.add_view(submit_view, route_name='v1_submit', renderer='json')


def check_cell_or_wifi(data, errors):
    cell = data.get('cell', ())
    wifi = data.get('wifi', ())

    if any(cell) and data['radio'] == '':
        # Skip the whole set of CellMeasure records
        return False

    # Clean up the cell data
    skips = set()
    for idx, c in enumerate(cell):
        if c['radio'] == '':
            skips.add(idx)

    skips = list(skips)
    skips.sort(reverse=True)
    for idx in skips:
        del cell[idx]
    data['cell'] = tuple(cell)

    if not any(wifi) and not any(cell):
        return False
    return True


def submit_validator(data, errors):
    # for each of the measurements, if the lat or lon is -255
    # drop the node
    skips = set()
    for idx, item in enumerate(data.get('items', ())):
        if item['lat'] == -255 or item['lon'] == -255:
            skips.add(idx)

        if not check_cell_or_wifi(item, errors):
            skips.add(idx)

    skips = list(skips)
    skips.sort(reverse=True)
    for idx in skips:
        del data['items'][idx]

    if errors:
        # don't add this error if something else was already wrong
        return


def check_geoip(request, data, errors):
    # Verify that the request comes from the same country as the lat/lon.
    if request.client_addr:
        geoip = request.registry.geoip_db.geoip_lookup(request.client_addr)
        if geoip:
            for item in data['items']:
                lat = float(item['lat'])
                lon = float(item['lon'])
                country = geoip['country_code']
                found = False
                for c in country_subunits_by_iso_code(country):
                    (lon1, lat1, lon2, lat2) = c.bbox
                    if lon1 <= lon and lon <= lon2 and \
                       lat1 <= lat and lat <= lat2:
                        found = True
                        break
                if not found:
                    heka_client = get_heka_client()
                    heka_client.incr("submit.geoip_mismatch")
                    desc = 'Submitted lat/lon does not match GeoIP.'
                    errors.append(dict(name=None, description=desc))


@check_api_key('submit')
def submit_view(request):
    data, errors = preprocess_request(
        request,
        schema=SubmitSchema(),
        extra_checks=(submit_validator,
                      lambda d, e: check_geoip(request, d, e), ),
    )

    items = data['items']
    nickname = request.headers.get('X-Nickname', u'')
    if isinstance(nickname, str):
        nickname = nickname.decode('utf-8', 'ignore')
    # batch incoming data into multiple tasks, in case someone
    # manages to submit us a huge single request
    for i in range(0, len(items), 100):
        insert_measures.delay(
            items=dumps(items[i:i + 100]),
            nickname=nickname,
        )
    return HTTPNoContent()
