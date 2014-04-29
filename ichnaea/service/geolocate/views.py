from pyramid.httpexceptions import HTTPError
from pyramid.httpexceptions import HTTPNotFound
from pyramid.response import Response

from ichnaea.decimaljson import dumps
from ichnaea.exceptions import BaseJSONError
from ichnaea.heka_logging import get_heka_client
from ichnaea.service.geolocate.schema import GeoLocateSchema
from ichnaea.service.error import (
    MSG_ONE_OF,
    preprocess_request,
)
from ichnaea.service.base import check_api_key
from ichnaea.service.search.views import (
    search_cell,
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


@check_api_key('geolocate', True)
def geolocate_view(request):
    heka_client = get_heka_client()

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
        if result is not None:
            heka_client.incr('geolocate.wifi_hit')
    else:
        result = search_cell_tower(session, data)
        if result is not None:
            heka_client.incr('geolocate.cell_hit')

    if result is None and request.client_addr:
        result = search_geoip(request.registry.geoip_db,
                              request.client_addr)
        if result is not None:
            heka_client.incr('geolocate.geoip_hit')

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
