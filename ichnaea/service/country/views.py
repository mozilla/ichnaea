from pyramid.httpexceptions import (
    HTTPNotFound,
    HTTPOk,
)

from ichnaea.service.error import (
    JSONParseError,
    preprocess_request,
)
from ichnaea.locate.location_searcher import CountrySearcher
from ichnaea.service.base import prepare_search_data
from ichnaea.service.geolocate.schema import GeoLocateSchema
from ichnaea.service.geolocate.views import NOT_FOUND

EMPTY = ('{}', '')


def configure_country(config):
    config.add_route('v1_country', '/v1/country')
    config.add_view(country_view, route_name='v1_country', renderer='json')


# Disable API key checks and logging for this API, for the initial wave
# @check_api_key('country', error_on_invalidkey=False)
def country_view(request):
    if (
            request.body in EMPTY and
            request.client_addr and
            request.registry.geoip_db is not None
    ):
        # Optimize common case of geoip-only request
        country = request.registry.geoip_db.country_lookup(request.client_addr)
        if country:
            response = HTTPOk()
            response.content_type = 'application/json'
            response.text = '{"country_code": "%s", "country_name": "%s"}' % (
                country.code, country.name)
            return response
        else:
            response = HTTPNotFound()
            response.content_type = 'application/json'
            response.body = NOT_FOUND
            return response

    request_data, errors = preprocess_request(
        request,
        schema=GeoLocateSchema(),
        response=JSONParseError,
        accept_empty=True,
    )

    search_data = prepare_search_data(
        request_data, client_addr=request.client_addr)

    response = CountrySearcher(
        session_db=request.db_ro_session,
        geoip_db=request.registry.geoip_db,
        api_key_log=False,
        api_key_name=None,
        api_name='country',
    ).search(search_data)

    if not response:
        response = HTTPNotFound()
        response.content_type = 'application/json'
        response.body = NOT_FOUND
        return response

    return response
