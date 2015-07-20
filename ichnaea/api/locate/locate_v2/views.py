from ichnaea.api.locate.locate_v2.schema import LocateV2Schema
from ichnaea.api.locate.views import BasePositionView


class LocateV2View(BasePositionView):

    route = '/v1/geolocate'
    view_name = 'geolocate'
    schema = LocateV2Schema

    def prepare_response(self, result):
        response = {
            'location': {
                'lat': result['lat'],
                'lng': result['lon'],
            },
            'accuracy': float(result['accuracy']),
        }

        if result['fallback']:
            response['fallback'] = result['fallback']

        return response
