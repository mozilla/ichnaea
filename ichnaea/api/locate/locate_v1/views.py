from ichnaea.api.error import JSONError
from ichnaea.api.locate.locate_v1.schema import LocateV1Schema
from ichnaea.api.locate.views import BaseLocateView


class LocateV1View(BaseLocateView):

    error_response = JSONError
    route = '/v1/search'
    schema = LocateV1Schema
    view_name = 'search'

    def not_found(self):
        return {'status': 'not_found'}

    def prepare_location_data(self, location_data):
        response = {
            'status': 'ok',
            'lat': location_data['lat'],
            'lon': location_data['lon'],
            'accuracy': location_data['accuracy'],
        }

        if location_data['fallback']:
            response['fallback'] = location_data['fallback']

        return response
