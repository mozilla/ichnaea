from pyramid.httpexceptions import HTTPNotFound

from ichnaea.decimaljson import dumps
from ichnaea.heka_logging import get_heka_client
from ichnaea.service.geolocate.schema import GeoLocateSchema
from ichnaea.service.error import (
    MSG_BAD_RADIO,
    MSG_ONE_OF,
    preprocess_request,
)
from ichnaea.service.base import check_api_key
from ichnaea.service.errors import JSONError
from ichnaea.service.search.views import (
    search_cell,
    search_cell_lac,
    search_geoip,
    search_wifi,
)


NOT_FOUND = {
    "error": {
        "errors": [{
            "domain": "geolocation",
            "reason": "notFound",
            "message": "Not found",
        }],
        "code": 404,
        "message": "Not found",
    }
}
NOT_FOUND = dumps(NOT_FOUND)


def configure_geolocate(config):
    config.add_route('v1_geolocate', '/v1/geolocate')
    config.add_view(geolocate_view, route_name='v1_geolocate', renderer='json')


def geolocate_validator(data, errors):
    if errors:
        # don't add this error if something else was already wrong
        return
    cell = data.get('cellTowers', ())
    wifi = data.get('wifiAccessPoints', ())

    # If a radio field is populated in any one of the cells in
    # cellTowers, this is a buggy geolocate call from FirefoxOS.
    # Just assume that we want to use the radio field in cellTowers
    if data['radioType'] == '':
        for c in cell:
            cell_radio = c['radio']
            if cell_radio != '' and data['radioType'] == '':
                data['radioType'] = cell_radio
            elif cell_radio != '' and data['radioType'] != cell_radio:
                errors.append(dict(name='body', description=MSG_BAD_RADIO))
                break

    if not any(wifi) and not any(cell):
        errors.append(dict(name='body', description=MSG_ONE_OF))


def search_cell_tower(session, data):
    mapped = {
        'radio': data['radioType'],
        'cell': [],
    }
    for cell in data['cellTowers']:
        mapped['cell'].append({
            'mcc': cell['mobileCountryCode'],
            'mnc': cell['mobileNetworkCode'],
            'lac': cell['locationAreaCode'],
            'cid': cell['cellId'],
        })
    return search_cell(session, mapped)


def search_cell_tower_lac(session, data):
    mapped = {
        'radio': data['radioType'],
        'cell': [],
    }
    for cell in data['cellTowers']:
        mapped['cell'].append({
            'mcc': cell['mobileCountryCode'],
            'mnc': cell['mobileNetworkCode'],
            'lac': cell['locationAreaCode'],
            'cid': cell['cellId'],
        })
    return search_cell_lac(session, mapped)


def search_wifi_ap(session, data):
    mapped = {
        'wifi': [],
    }
    for wifi in data['wifiAccessPoints']:
        mapped['wifi'].append({
            'key': wifi['macAddress'],
        })
    return search_wifi(session, mapped)


@check_api_key('geolocate', True)
def geolocate_view(request):
    heka_client = get_heka_client()

    data, errors = preprocess_request(
        request,
        schema=GeoLocateSchema(),
        extra_checks=(geolocate_validator, ),
        response=JSONError,
        accept_empty=True,
    )

    session = request.db_slave_session
    result = None

    if data and data['wifiAccessPoints']:
        result = search_wifi_ap(session, data)
        if result is not None:
            heka_client.incr('geolocate.wifi_hit')
            heka_client.timer_send('geolocate.accuracy.wifi',
                                   result['accuracy'])
    elif data:
        result = search_cell_tower(session, data)
        if result is not None:
            heka_client.incr('geolocate.cell_hit')
            heka_client.timer_send('geolocate.accuracy.cell',
                                   result['accuracy'])

        if result is None:
            result = search_cell_tower_lac(session, data)
            if result is not None:
                heka_client.incr('geolocate.cell_lac_hit')
                heka_client.timer_send('geolocate.accuracy.cell_lac',
                                       result['accuracy'])

    if result is None and request.client_addr:
        result = search_geoip(request.registry.geoip_db,
                              request.client_addr)
        if result is not None:
            heka_client.incr('geolocate.geoip_hit')
            heka_client.timer_send('geolocate.accuracy.geoip',
                                   result['accuracy'])

    if result is None:
        heka_client.incr('geolocate.miss')
        result = HTTPNotFound()
        result.content_type = 'application/json'
        result.body = NOT_FOUND
        return result

    return {
        "location": {
            "lat": result['lat'],
            "lng": result['lon'],
        },
        "accuracy": float(result['accuracy']),
    }
