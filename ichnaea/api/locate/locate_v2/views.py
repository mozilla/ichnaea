from ichnaea.api.locate.locate_v2.schema import LocateV2Schema
from ichnaea.api.locate.views import BaseLocateView


class LocateV2View(BaseLocateView):

    route = '/v1/geolocate'
    view_name = 'geolocate'
    schema = LocateV2Schema

    def prepare_location_data(self, location_data):
        response = {
            'location': {
                'lat': location_data['lat'],
                'lng': location_data['lon'],
            },
            'accuracy': float(location_data['accuracy']),
        }

        if location_data['fallback']:
            response['fallback'] = location_data['fallback']

        return response
