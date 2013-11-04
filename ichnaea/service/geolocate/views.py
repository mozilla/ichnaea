import logging

from cornice import Service
from pyramid.httpexceptions import HTTPError
from pyramid.httpexceptions import HTTPNotFound
from pyramid.response import Response

from ichnaea.decimaljson import dumps
from ichnaea.service.geolocate.schema import GeoLocateSchema
from ichnaea.service.error import (
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

PARSE_ERROR = {
    "error": {
        "errors": [{
            "domain": "global",
            "reason": "parseError",
            "message": "Parse Error",
        }],
        "code": 400,
        "message": "Parse Error"
    }
}
PARSE_ERROR = dumps(PARSE_ERROR)


class _JSONError(HTTPError):
    def __init__(self, errors, status=400):
        Response.__init__(self, PARSE_ERROR)
        self.status = status
        self.content_type = 'application/json'


def error_handler(errors):
    # filter out the rather common MSG_ONE_OF errors
    log_errors = []
    for error in errors:
        if error.get('description', '') != MSG_ONE_OF:
            log_errors.append(error)
    if log_errors:
        logger.debug('error_handler' + repr(log_errors))
    return _JSONError(errors, errors.status)


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
