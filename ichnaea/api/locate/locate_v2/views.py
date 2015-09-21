from ichnaea.api.locate.locate_v2.schema import LOCATE_V2_SCHEMA
from ichnaea.api.locate.views import BasePositionView


class LocateV2View(BasePositionView):

    metric_path = 'v1.geolocate'  #:
    route = '/v1/geolocate'  #:
    schema = LOCATE_V2_SCHEMA  #:

    def prepare_response(self, result):
        response = {
            'location': {
                'lat': result['lat'],
                'lng': result['lon'],
            },
            'accuracy': result['accuracy'],
        }

        if result['fallback']:
            response['fallback'] = result['fallback']

        return response
