from ichnaea.service.base_locate import BaseLocateView


class GeolocateView(BaseLocateView):

    route = '/v1/geolocate'
    view_name = 'geolocate'

    def view(self, api_key):
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
