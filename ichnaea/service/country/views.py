from ichnaea.models import ApiKey
from ichnaea.locate.searcher import CountrySearcher
from ichnaea.service.base_locate import BaseLocateView


class CountryView(BaseLocateView):

    error_on_invalidkey = False
    searcher = CountrySearcher
    route = '/v1/country'
    view_name = 'country'

    # TODO: Disable API key checks and logging, for the initial wave
    # @check_api_key()
    def __call__(self):
        api_key = ApiKey(valid_key=None)
        result = self.locate(api_key)
        if not result:
            return self.not_found()

        return result
