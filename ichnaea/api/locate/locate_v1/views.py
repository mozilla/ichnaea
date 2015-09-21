from ichnaea.api.exceptions import LocationNotFoundV1
from ichnaea.api.locate.locate_v1.schema import LOCATE_V1_SCHEMA
from ichnaea.api.locate.views import BasePositionView


class LocateV1View(BasePositionView):

    metric_path = 'v1.search'  #:
    not_found = LocationNotFoundV1  #:
    route = '/v1/search'  #:
    schema = LOCATE_V1_SCHEMA  #:

    def prepare_response(self, result):
        response = {
            'status': 'ok',
            'lat': result['lat'],
            'lon': result['lon'],
            'accuracy': result['accuracy'],
        }

        if result['fallback']:
            response['fallback'] = result['fallback']

        return response
