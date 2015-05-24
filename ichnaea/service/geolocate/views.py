from pyramid.httpexceptions import HTTPNotFound

from ichnaea.customjson import dumps
from ichnaea.service.geolocate.schema import GeoLocateSchema
from ichnaea.service.error import (
    JSONParseError,
    preprocess_request,
)
from ichnaea.locate.searcher import PositionSearcher
from ichnaea.service.base import check_api_key
from ichnaea.service.base_locate import (
    BaseLocateView,
    prepare_locate_query,
)


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
    config.add_view(GeolocateView, route_name='v1_geolocate', renderer='json')


class GeolocateView(BaseLocateView):

    view_name = 'geolocate'

    @check_api_key()
    def __call__(self, api_key):
        request = self.request
        request_data, errors = preprocess_request(
            request,
            schema=GeoLocateSchema(),
            response=JSONParseError,
            accept_empty=True,
        )
        query = prepare_locate_query(
            request_data, client_addr=request.client_addr)

        result = PositionSearcher(
            session_db=request.db_ro_session,
            geoip_db=request.registry.geoip_db,
            redis_client=request.registry.redis_client,
            settings=request.registry.settings,
            api_key=api_key,
            api_name='geolocate',
        ).search(query)

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
