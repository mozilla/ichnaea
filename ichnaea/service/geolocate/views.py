from pyramid.httpexceptions import HTTPError
from pyramid.httpexceptions import HTTPNotFound
from pyramid.response import Response

from ichnaea.decimaljson import dumps
from ichnaea.exceptions import BaseJSONError
from ichnaea.service.geolocate.schema import GeoLocateSchema
from ichnaea.service.error import (
    MSG_BAD_RADIO,
    MSG_ONE_OF,
    preprocess_request,
)
from ichnaea.service.base import check_api_key
from ichnaea.service.search.views import (
    search_all_sources,
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


def map_data(data):
    """
    Transform a geolocate API dictionary to an equivalent search API
    dictionary.
    """
    if not data:
        return data

    mapped = {
        'radio': data['radioType'],
        'cell': [],
        'wifi': [],
    }

    if 'cellTowers' in data:
        mapped['cell'] = [{
            'mcc': cell['mobileCountryCode'],
            'mnc': cell['mobileNetworkCode'],
            'lac': cell['locationAreaCode'],
            'cid': cell['cellId'],
        } for cell in data['cellTowers']]

    if 'wifiAccessPoints' in data:
        mapped['wifi'] = [{
            'key': wifi['macAddress'],
        } for wifi in data['wifiAccessPoints']]

    return mapped


@check_api_key('geolocate', True)
def geolocate_view(request):

    data, errors = preprocess_request(
        request,
        schema=GeoLocateSchema(),
        extra_checks=(geolocate_validator, ),
        response=JSONError,
        accept_empty=True,
    )

    data = map_data(data)
    result = search_all_sources(request, data, "geolocate")

    if not result:
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
