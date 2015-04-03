from pyramid.httpexceptions import HTTPNotFound

from ichnaea.customjson import dumps
from ichnaea.service.geolocate.schema import GeoLocateSchema
from ichnaea.service.error import (
    JSONParseError,
    preprocess_request,
)
from ichnaea.locate.searcher import PositionSearcher
from ichnaea.service.base import check_api_key, prepare_search_data


NOT_FOUND = {
    'error': {
        'errors': [{
            'domain': 'geolocation',
            'reason': 'notFound',
            'message': 'Not found',
        }],
        'code': 404,
        'message': 'Not found',
    }
}
NOT_FOUND = dumps(NOT_FOUND)


def configure_geolocate(config):
    config.add_route('v1_geolocate', '/v1/geolocate')
    config.add_view(geolocate_view, route_name='v1_geolocate', renderer='json')


@check_api_key('geolocate')
def geolocate_view(request, api_key):
    request_data, errors = preprocess_request(
        request,
        schema=GeoLocateSchema(),
        response=JSONParseError,
        accept_empty=True,
    )
    search_data = prepare_search_data(
        request_data, client_addr=request.client_addr)

    result = PositionSearcher(
        session_db=request.db_ro_session,
        geoip_db=request.registry.geoip_db,
        settings=request.registry.settings,
        api_key=api_key,
        api_name='geolocate',
    ).search(search_data)

    if not result:
        result = HTTPNotFound()
        result.content_type = 'application/json'
        result.body = NOT_FOUND
        return result

    return {
        'location': {
            'lat': result['lat'],
            'lng': result['lon'],
        },
        'accuracy': float(result['accuracy']),
    }
