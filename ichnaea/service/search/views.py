from ichnaea.service.base import check_api_key
from ichnaea.service.locate import search_all_sources
from ichnaea.service.error import (
    MSG_ONE_OF,
    preprocess_request,
)
from ichnaea.service.search.schema import SearchSchema


def configure_search(config):
    config.add_route('v1_search', '/v1/search')
    config.add_view(search_view, route_name='v1_search', renderer='json')


def check_cell_or_wifi(data, errors):
    if errors:  # pragma: no cover
        # don't add this error if something else was already wrong
        return

    cell = data.get('cell', ())
    wifi = data.get('wifi', ())
    if not any(wifi) and not any(cell):
        errors.append(dict(name='body', description=MSG_ONE_OF))


@check_api_key('search', True)
def search_view(request):
    data, errors = preprocess_request(
        request,
        schema=SearchSchema(),
        extra_checks=(check_cell_or_wifi, ),
        accept_empty=True,
    )

    session = request.db_slave_session
    result = search_all_sources(
        session, 'search', data,
        client_addr=request.client_addr,
        geoip_db=request.registry.geoip_db)

    if not result:
        return {'status': 'not_found'}

    return {
        'status': 'ok',
        'lat': result['lat'],
        'lon': result['lon'],
        'accuracy': result['accuracy'],
    }
