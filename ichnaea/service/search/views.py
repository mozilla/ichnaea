from ichnaea.service.base import check_api_key
from ichnaea.service.error import preprocess_request
from ichnaea.locate.searcher import PositionSearcher
from ichnaea.service.search.schema import SearchSchema


def configure_search(config):
    config.add_route('v1_search', '/v1/search')
    config.add_view(search_view, route_name='v1_search', renderer='json')


def prepare_search_data(request_data, client_addr=None):
    search_data = {
        'geoip': client_addr,
        'cell': [],
        'wifi': [],
    }
    if request_data:
        if 'cell' in request_data:
            for cell in request_data['cell']:
                new_cell = {
                    'mcc': cell['mcc'],
                    'mnc': cell['mnc'],
                    'lac': cell['lac'],
                    'cid': cell['cid'],
                }
                # Use a per-cell radio if present
                if 'radio' in cell and cell['radio']:
                    new_cell['radio'] = cell['radio']
                # Fall back to a top-level radio field
                if 'radio' not in new_cell:
                    new_cell['radio'] = request_data.get('radio', None)
                search_data['cell'].append(new_cell)

        if 'wifi' in request_data:
            for wifi in request_data['wifi']:
                new_wifi = {
                    'key': wifi['key'],
                    'signal': wifi['signal'],
                }
                search_data['wifi'].append(new_wifi)

    return search_data


@check_api_key('search')
def search_view(request, api_key):
    request_data, errors = preprocess_request(
        request,
        schema=SearchSchema(),
        accept_empty=True,
    )
    search_data = prepare_search_data(
        request_data, client_addr=request.client_addr)

    result = PositionSearcher(
        session_db=request.db_ro_session,
        geoip_db=request.registry.geoip_db,
        settings=request.registry.settings,
        api_key=api_key,
        api_name='search',
    ).search(search_data)

    if not result:
        return {'status': 'not_found'}

    return {
        'status': 'ok',
        'lat': result['lat'],
        'lon': result['lon'],
        'accuracy': result['accuracy'],
    }
