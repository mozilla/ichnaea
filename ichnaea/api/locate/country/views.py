from ichnaea.api.locate.searcher import CountrySearcher
from ichnaea.api.locate.views import BaseLocateView


class CountryView(BaseLocateView):

    # TODO: Disable API key checks and logging, for the initial wave
    check_api_key = False
    error_on_invalidkey = False
    searcher = CountrySearcher
    route = '/v1/country'
    view_name = 'country'

    def view(self, api_key):
        result = self.locate(api_key)
        if not result:
            return self.not_found()

        return result
