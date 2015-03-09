from ichnaea.service.base import check_api_key
from ichnaea.service.error import preprocess_request
from ichnaea.locate.location_searcher import PositionSearcher
from ichnaea.service.search.schema import SearchSchema


def configure_search(config):
    config.add_route('v1_search', '/v1/search')
    config.add_view(search_view, route_name='v1_search', renderer='json')


@check_api_key('search')
def search_view(request):
    data, errors = preprocess_request(
        request,
        schema=SearchSchema(),
        accept_empty=True,
    )

    data['geoip'] = request.client_addr
    session = request.db_ro_session
    result = PositionSearcher(
        {'geoip': request.registry.geoip_db, 'session': session},
        api_key_log=getattr(request, 'api_key_log', False),
        api_key_name=getattr(request, 'api_key_name', None),
        api_name='search',
    ).search(data)

    if not result:
        return {'status': 'not_found'}

    return {
        'status': 'ok',
        'lat': result['lat'],
        'lon': result['lon'],
        'accuracy': result['accuracy'],
    }
