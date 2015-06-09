from ichnaea.api.locate.searcher import CountrySearcher
from ichnaea.api.locate.locate_v2.views import LocateV2View


class CountryView(LocateV2View):

    # TODO: Disable API key checks and logging, for the initial wave
    check_api_key = False
    error_on_invalidkey = False
    searcher = CountrySearcher
    route = '/v1/country'
    view_name = 'country'

    def prepare_location_data(self, location_data):
        return location_data
