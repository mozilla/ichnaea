import logging

from cornice import Service
from pyramid.httpexceptions import HTTPNotFound

from ichnaea.decimaljson import dumps
from ichnaea.service.geolocate.schema import GeoLocateSchema
from ichnaea.service.error import (
    error_handler,
    MSG_ONE_OF,
)
from ichnaea.service.search.views import (
    search_cell,
    search_wifi,
)

logger = logging.getLogger('ichnaea')
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
    config.scan('ichnaea.service.geolocate.views')


def geolocate_validator(request):
    if len(request.errors):
        return
    data = request.validated
    cell = data.get('cellTowers', ())
    wifi = data.get('wifiAccessPoints', ())
    if not any(wifi) and not any(cell):
        request.errors.add('body', 'body', MSG_ONE_OF)


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


def search_wifi_ap(session, data):
    mapped = {
        'wifi': [],
    }
    for wifi in data['wifiAccessPoints']:
        mapped['wifi'].append({
            'key': wifi['macAddress'],
        })
    return search_wifi(session, mapped)


geolocate = Service(
    name='geolocate',
    path='/v1/geolocate',
    description="Geolocate yourself.",
)


@geolocate.post(renderer='json', accept="application/json",
                schema=GeoLocateSchema, error_handler=error_handler,
                validators=geolocate_validator)
def geolocate_post(request):
    data = request.validated
    session = request.db_slave_session

    result = None
    if data['wifiAccessPoints']:
        result = search_wifi_ap(session, data)
    else:
        result = search_cell_tower(session, data)
    if result is None:
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
