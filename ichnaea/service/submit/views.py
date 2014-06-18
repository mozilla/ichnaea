from pyramid.httpexceptions import HTTPNoContent

from ichnaea.customjson import dumps
from ichnaea.geocalc import location_is_in_country
from ichnaea.heka_logging import get_heka_client
from ichnaea.service.error import (
    preprocess_request,
)
from ichnaea.service.submit.schema import SubmitSchema
from ichnaea.service.submit.tasks import insert_measures
from ichnaea.service.base import check_api_key


def configure_submit(config):
    config.add_route('v1_submit', '/v1/submit')
    config.add_view(submit_view, route_name='v1_submit', renderer='json')


def check_cell_or_wifi(data, errors):
    cell = data.get('cell', ())
    wifi = data.get('wifi', ())

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
        if geoip and 'items' in data:
            filtered_items = []
            for item in data['items']:
                lat = float(item['lat'])
                lon = float(item['lon'])
                country = geoip['country_code']
                if location_is_in_country(lat, lon, country, 1):
                    filtered_items.append(item)
                else:
                    heka_client = get_heka_client()
                    heka_client.incr("submit.geoip_mismatch")
            data['items'] = filtered_items


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
