from ichnaea.api.locate.locate_v2.views import LocateV2View


class CountryView(LocateV2View):

    # TODO: Disable API key checks and logging, for the initial wave
    check_api_key = False
    error_on_invalidkey = False
    searcher = 'country_searcher'
    route = '/v1/country'
    view_name = 'country'

    def prepare_location_data(self, location_data):
        response = {
            'country_code': location_data['country_code'],
            'country_name': location_data['country_name'],
        }

        if location_data['fallback']:
            response['fallback'] = location_data['fallback']

        return response
