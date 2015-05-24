from ichnaea.models import ApiKey
from ichnaea.locate.searcher import CountrySearcher
from ichnaea.service.base_locate import BaseLocateView


def configure_country(config):
    config.add_route('v1_country', '/v1/country')
    config.add_view(CountryView, route_name='v1_country', renderer='json')


class CountryView(BaseLocateView):

    error_on_invalidkey = False
    searcher = CountrySearcher
    view_name = 'country'

    # TODO: Disable API key checks and logging, for the initial wave
    # @check_api_key()
    def __call__(self):
        api_key = ApiKey()
        result = self.locate(api_key)
        if not result:
            return self.not_found()

        return result
