from ichnaea.models.transform import ReportTransform
from ichnaea.service.base_locate import BaseLocateView
from ichnaea.service.error import JSONError
from ichnaea.service.locate1.schema import Locate1Schema


class Locate1Transform(ReportTransform):

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


class Locate1View(BaseLocateView):

    error_response = JSONError
    route = '/v1/search'
    schema = Locate1Schema
    transform = Locate1Transform
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
