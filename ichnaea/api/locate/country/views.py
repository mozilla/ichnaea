from ichnaea.api.locate.locate_v2.views import LocateV2View


class CountryView(LocateV2View):

    # TODO: Disable API key checks and logging, for the initial wave
    check_api_key = False  #:
    error_on_invalidkey = False  #:
    searcher = 'country_searcher'  #:
    route = '/v1/country'  #:
    view_name = 'country'  #:
    view_type = 'country'  #:

    def prepare_response(self, result):
        response = {
            'country_code': result['country_code'],
            'country_name': result['country_name'],
        }

        if result['fallback']:
            response['fallback'] = result['fallback']

        return response
