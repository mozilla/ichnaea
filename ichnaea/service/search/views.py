from ichnaea.models.transform import ReportTransform
from ichnaea.locate.searcher import PositionSearcher
from ichnaea.service.base import check_api_key
from ichnaea.service.base_locate import BaseLocateView
from ichnaea.service.error import preprocess_request
from ichnaea.service.search.schema import SearchSchema


def configure_search(config):
    config.add_route('v1_search', '/v1/search')
    config.add_view(SearchView, route_name='v1_search', renderer='json')


class SearchTransform(ReportTransform):

    radio_id = ('radio', 'radio')
    cell_id = ('cell', 'cell')
    cell_map = [
        ('radio', 'radio'),
        ('mcc', 'mcc'),
        ('mnc', 'mnc'),
        ('lac', 'lac'),
        ('cid', 'cid'),
        ('signal', 'signal'),
        ('ta', 'ta'),
        ('psc', 'psc'),
    ]

    wifi_id = ('wifi', 'wifi')
    wifi_map = [
        ('key', 'key'),
        ('channel', 'channel'),
        ('frequency', 'frequency'),
        ('signal', 'signal'),
        ('signalToNoiseRatio', 'snr'),
    ]


def prepare_locate_query(request_data, client_addr=None):
    transform = SearchTransform()
    parsed_data = transform.transform_one(request_data)

    query = {'geoip': client_addr}
    query['cell'] = parsed_data.get('cell', [])
    query['wifi'] = parsed_data.get('wifi', [])
    return query


class SearchView(BaseLocateView):

    @check_api_key('search')
    def __call__(self, api_key):
        request = self.request
        request_data, errors = preprocess_request(
            request,
            schema=SearchSchema(),
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
            api_name='search',
        ).search(query)

        if not result:
            return {'status': 'not_found'}

        return {
            'status': 'ok',
            'lat': result['lat'],
            'lon': result['lon'],
            'accuracy': result['accuracy'],
        }
