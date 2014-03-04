from pyramid.httpexceptions import HTTPError
from pyramid.httpexceptions import HTTPNotFound, HTTPBadRequest
from pyramid.response import Response

from heka.holder import get_client

from ichnaea.decimaljson import dumps
from ichnaea.exceptions import BaseJSONError
from ichnaea.service.geolocate.schema import GeoLocateSchema
from ichnaea.service.error import (
    MSG_ONE_OF,
    preprocess_request,
)
from ichnaea.service.search.views import (
    search_cell,
    search_wifi,
)

NO_API_KEY = {
    "error": {
        "errors": [{
            "domain": "usageLimits",
            "reason": "keyInvalid",
            "message": "No API key was found",
        }],
        "code": 400,
        "message": "No API key",
    }
}
NO_API_KEY = dumps(NO_API_KEY)

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


class JSONError(HTTPError, BaseJSONError):
    def __init__(self, errors, status=400):
        Response.__init__(self, PARSE_ERROR)
        self.status = status
        self.content_type = 'application/json'


def configure_geolocate(config):
    config.add_route('v1_geolocate', '/v1/geolocate')
    config.add_view(geolocate_view, route_name='v1_geolocate', renderer='json')


def geolocate_validator(data, errors):
    if errors:
        # don't add this error if something else was already wrong
        return
    cell = data.get('cellTowers', ())
    wifi = data.get('wifiAccessPoints', ())
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


def search_wifi_ap(session, data):
    mapped = {
        'wifi': [],
    }
    for wifi in data['wifiAccessPoints']:
        mapped['wifi'].append({
            'key': wifi['macAddress'],
        })
    return search_wifi(session, mapped)


def geolocate_view(request):
    api_key = request.GET.get('key', None)
    if api_key is None:
        result = HTTPBadRequest()
        result.content_type = 'application/json'
        result.body = NO_API_KEY
        return result

    heka_client = get_client('ichnaea')
    heka_client.incr('geolocate.api_key.%s' % api_key)

    data, errors = preprocess_request(
        request,
        schema=GeoLocateSchema(),
        extra_checks=(geolocate_validator, ),
        response=JSONError,
    )

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
