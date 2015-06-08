from ichnaea.api.error import JSONError
from ichnaea.api.locate.locate_v1.schema import LocateV1Schema
from ichnaea.api.locate.views import BaseLocateView
from ichnaea.models.transform import ReportTransform


class LocateV1Transform(ReportTransform):

    radio_id = ('radio', 'radio')
    cell_id = ('cell', 'cell')
    cell_map = [
        'radio',
        'mcc',
        'mnc',
        'lac',
        'cid',
        'signal',
        'ta',
        'psc',
    ]

    wifi_id = ('wifi', 'wifi')
    wifi_map = [
        'key',
        'channel',
        'frequency',
        'signal',
        ('signalToNoiseRatio', 'snr'),
    ]


class LocateV1View(BaseLocateView):

    error_response = JSONError
    route = '/v1/search'
    schema = LocateV1Schema
    transform = LocateV1Transform
    view_name = 'search'

    def not_found(self):
        return {'status': 'not_found'}

    def view(self, api_key):
        location_data = self.locate(api_key)
        if not location_data:
            return self.not_found()

        response = {
            'status': 'ok',
            'lat': location_data['lat'],
            'lon': location_data['lon'],
            'accuracy': location_data['accuracy'],
        }

        if location_data['fallback']:
            response['fallback'] = location_data['fallback']

        return response
