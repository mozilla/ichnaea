from pyramid.httpexceptions import HTTPNotFound

from ichnaea.customjson import dumps
from ichnaea.service.geolocate.schema import GeoLocateSchema
from ichnaea.service.error import (
    JSONParseError,
    preprocess_request,
)
from ichnaea.service.base import check_api_key
from ichnaea.service.locate import (
    search_all_sources,
    map_data,
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


@check_api_key('geolocate')
def geolocate_view(request):

    data, errors = preprocess_request(
        request,
        schema=GeoLocateSchema(),
        response=JSONParseError,
        accept_empty=True,
    )

    data = map_data(data)
    session = request.db_slave_session
    result = search_all_sources(
        session, 'geolocate', data,
        client_addr=request.client_addr,
        geoip_db=request.registry.geoip_db,
        api_key_log=getattr(request, 'api_key_log', False),
        api_key_name=getattr(request, 'api_key_name', None))

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
