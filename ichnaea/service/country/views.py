from pyramid.httpexceptions import HTTPNotFound

from ichnaea.models import ApiKey
from ichnaea.locate.searcher import CountrySearcher
from ichnaea.service.base_locate import (
    BaseLocateView,
    prepare_locate_query,
)
from ichnaea.service.error import (
    JSONParseError,
    preprocess_request,
)
from ichnaea.service.geolocate.schema import GeoLocateSchema
from ichnaea.service.geolocate.views import NOT_FOUND


def configure_country(config):
    config.add_route('v1_country', '/v1/country')
    config.add_view(CountryView, route_name='v1_country', renderer='json')


class CountryView(BaseLocateView):

    error_on_invalidkey = False
    view_name = 'country'

    # TODO: Disable API key checks and logging, for the initial wave
    # @check_api_key()
    def __call__(self):
        request = self.request
        request_data, errors = preprocess_request(
            request,
            schema=GeoLocateSchema(),
            response=JSONParseError,
            accept_empty=True,
        )
        query = prepare_locate_query(
            request_data, client_addr=request.client_addr)

        response = CountrySearcher(
            session_db=request.db_ro_session,
            geoip_db=request.registry.geoip_db,
            redis_client=request.registry.redis_client,
            settings=request.registry.settings,
            api_key=ApiKey(),
            api_name='country',
        ).search(query)

        if not response:
            response = HTTPNotFound()
            response.content_type = 'application/json'
            response.body = NOT_FOUND
            return response

        return response
