from ichnaea.api.exceptions import LocationNotFoundV1
from ichnaea.api.locate.locate_v1.schema import LocateV1Schema
from ichnaea.api.locate.views import BasePositionView


class LocateV1View(BasePositionView):

    not_found = LocationNotFoundV1
    route = '/v1/search'
    schema = LocateV1Schema
    view_name = 'search'

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
