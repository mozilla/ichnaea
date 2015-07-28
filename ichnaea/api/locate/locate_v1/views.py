from ichnaea.api.exceptions import LocationNotFoundV1
from ichnaea.api.locate.locate_v1.schema import LocateV1Schema
from ichnaea.api.locate.views import BasePositionView


class LocateV1View(BasePositionView):

    metric_path = 'v1.search'  #:
    not_found = LocationNotFoundV1  #:
    route = '/v1/search'  #:
    schema = LocateV1Schema  #:

    def prepare_response(self, result):
        response = {
            'status': 'ok',
            'lat': result['lat'],
            'lon': result['lon'],
            'accuracy': int(result['accuracy']),
        }

        if result['fallback']:
            response['fallback'] = result['fallback']

        return response
