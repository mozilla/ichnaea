from ichnaea.models.transform import ReportTransform
from ichnaea.service.base import check_api_key
from ichnaea.service.base_locate import BaseLocateView
from ichnaea.service.error import JSONError
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


class SearchView(BaseLocateView):

    error_response = JSONError
    schema = SearchSchema
    transform = SearchTransform
    view_name = 'search'

    def not_found(self):
        return {'status': 'not_found'}

    @check_api_key()
    def __call__(self, api_key):
        result = self.locate(api_key)
        if not result:
            return self.not_found()

        return {
            'status': 'ok',
            'lat': result['lat'],
            'lon': result['lon'],
            'accuracy': result['accuracy'],
        }
