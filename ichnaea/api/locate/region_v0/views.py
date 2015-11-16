"""
Implementation of geodude compatibility API without allow_post support.

See also https://github.com/mozilla/geodude.
"""

from ichnaea.api.exceptions import (
    RegionNotFoundV0,
    RegionNotFoundV0JS,
)
from ichnaea.api.locate.views import BaseLocateView
from ichnaea.api.locate.query import Query


class RegionV0BaseView(BaseLocateView):

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

        raise self.not_found()


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
