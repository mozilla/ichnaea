from ichnaea.service.base import check_api_key
from ichnaea.service.base_locate import BaseLocateView


def configure_geolocate(config):
    config.add_route('v1_geolocate', '/v1/geolocate')
    config.add_view(GeolocateView, route_name='v1_geolocate', renderer='json')


class GeolocateView(BaseLocateView):

    view_name = 'geolocate'

    @check_api_key()
    def __call__(self, api_key):
        result = self.locate(api_key)
        if not result:
            return self.not_found()

        return {
            'location': {
                'lat': result['lat'],
                'lng': result['lon'],
            },
            'accuracy': float(result['accuracy']),
        }
