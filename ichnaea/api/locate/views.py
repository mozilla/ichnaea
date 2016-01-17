"""
Implementation of a locate specific HTTP service view.
"""

from ichnaea.api.exceptions import (
    LocationNotFound,
    LocationNotFoundV1,
    RegionNotFoundV0,
    RegionNotFoundV0JS,
)
from ichnaea.api.locate.schema_v1 import LOCATE_V1_SCHEMA
from ichnaea.api.locate.schema_v2 import LOCATE_V2_SCHEMA
from ichnaea.api.locate.query import Query
from ichnaea.api.views import BaseAPIView


class BaseLocateView(BaseAPIView):
    """Common base class for all locate related views."""

    #: :exc:`ichnaea.api.exceptions.LocationNotFound`
    not_found = LocationNotFound
    searcher = None  #:

    def locate(self, api_key):
        request_data, errors = self.preprocess_request()

        query = Query(
            fallback=request_data.get('fallbacks'),
            ip=self.request.client_addr,
            cell=request_data.get('cell'),
            wifi=request_data.get('wifi'),
            api_key=api_key,
            api_type=self.view_type,
            session=self.request.db_ro_session,
            http_session=self.request.registry.http_session,
            geoip_db=self.request.registry.geoip_db,
            stats_client=self.stats_client,
        )

        searcher = getattr(self.request.registry, self.searcher)
        return searcher.search(query)

    def prepare_response(self, response_data):  # pragma: no cover
        return response_data

    def view(self, api_key):
        """
        Execute the view code and return a response.
        """
        result = self.locate(api_key)
        if not result:
            raise self.prepare_exception(self.not_found())

        return self.prepare_response(result)


class BasePositionView(BaseLocateView):
    """Common base class for all position related views."""

    #: Use renderer with prettier float output.
    renderer = 'floatjson'  #:
    searcher = 'position_searcher'  #:
    view_type = 'locate'  #:


class LocateV1View(BasePositionView):

    metric_path = 'v1.search'  #:
    not_found = LocationNotFoundV1  #:
    route = '/v1/search'  #:
    schema = LOCATE_V1_SCHEMA  #:

    def prepare_response(self, result):
        response = {
            'status': 'ok',
            'lat': result['lat'],
            'lon': result['lon'],
            'accuracy': result['accuracy'],
        }

        if result['fallback']:
            response['fallback'] = result['fallback']

        return response


class LocateV2View(BasePositionView):

    metric_path = 'v1.geolocate'  #:
    route = '/v1/geolocate'  #:
    schema = LOCATE_V2_SCHEMA  #:

    def prepare_response(self, result):
        response = {
            'location': {
                'lat': result['lat'],
                'lng': result['lon'],
            },
            'accuracy': result['accuracy'],
        }

        if result['fallback']:
            response['fallback'] = result['fallback']

        return response


class RegionV0BaseView(BaseLocateView):
    """
    Implementation of geodude compatibility API
    without allow_post support.

    See also https://github.com/mozilla/geodude.
    """

    check_api_key = False  #:
    error_on_invalidkey = False  #:
    http_cache = (60, {'private': True,
                       's_maxage': 0,
                       'proxy_revalidate': True})  #:
    view_type = 'region'  #:

    def __call__(self):
        """Execute the view and return a response."""
        query = Query(
            ip=self.request.client_addr,
            api_type=self.view_type,
            geoip_db=self.request.registry.geoip_db,
        )

        geoip = query.geoip
        if geoip:
            return self.prepare_response(geoip)

        raise self.prepare_exception(self.not_found())


class RegionV0JSView(RegionV0BaseView):

    not_found = RegionNotFoundV0JS  #:
    metric_path = 'v0.country_js'  #:
    renderer = 'js'  #:
    route = '/country.js'  #:

    _template = u"""\
function geoip_country_code() { return '%s'; }
function geoip_country_name() { return '%s'; }
"""

    def prepare_response(self, result):
        return self._template % (
            result['region_code'],
            result['region_name'],
        )


class RegionV0JSONView(RegionV0BaseView):

    not_found = RegionNotFoundV0  #:
    metric_path = 'v0.country_json'  #:
    renderer = 'json'
    route = '/country.json'  #:

    def prepare_response(self, result):
        return {
            'country_code': result['region_code'],
            'country_name': result['region_name'],
        }


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
