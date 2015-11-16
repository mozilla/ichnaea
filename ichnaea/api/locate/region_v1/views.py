from ichnaea.api.locate.locate_v2.views import LocateV2View


class RegionV1View(LocateV2View):

    check_api_key = False  #:
    error_on_invalidkey = False  #:
    metric_path = 'v1.country'  #:
    renderer = 'json'
    route = '/v1/country'  #:
    searcher = 'region_searcher'  #:
    view_type = 'region'  #:

    def prepare_response(self, result):
        response = {
            'country_code': result['region_code'],
            'country_name': result['region_name'],
        }

        if result['fallback']:
            response['fallback'] = result['fallback']

        return response
