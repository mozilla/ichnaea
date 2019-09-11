"""
Implementation of locate specific HTTP service views.
"""

from ichnaea.api.exceptions import LocationNotFound, LocationNotFoundV0
from ichnaea.api.locate.schema_v0 import LOCATE_V0_SCHEMA
from ichnaea.api.locate.schema_v1 import LOCATE_V1_SCHEMA
from ichnaea.api.locate.query import Query
from ichnaea.api.views import BaseAPIView


class BaseLocateView(BaseAPIView):
    """Common base class for all locate related views."""

    not_found = LocationNotFound
    searcher = None

    def locate(self, api_key):
        request_data, errors = self.preprocess_request()

        query = Query(
            fallback=request_data.get("fallbacks"),
            ip=self.request.client_addr,
            blue=request_data.get("bluetoothBeacons"),
            cell=request_data.get("cellTowers"),
            wifi=request_data.get("wifiAccessPoints"),
            api_key=api_key,
            api_type=self.view_type,
            session=self.request.db_session,
            http_session=self.request.registry.http_session,
            geoip_db=self.request.registry.geoip_db,
            stats_client=self.stats_client,
        )

        searcher = getattr(self.request.registry, self.searcher)
        return searcher.search(query)

    def prepare_response(self, response_data):
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

    renderer = "json"
    searcher = "position_searcher"
    view_type = "locate"


class LocateV0View(BasePositionView):
    """View class for v1/search HTTP API."""

    metric_path = "v1.search"
    not_found = LocationNotFoundV0
    route = "/v1/search"
    schema = LOCATE_V0_SCHEMA

    def prepare_response(self, result):
        response = {
            "status": "ok",
            "lat": result["lat"],
            "lon": result["lon"],
            "accuracy": result["accuracy"],
        }

        if result["fallback"]:
            response["fallback"] = result["fallback"]

        return response


class LocateV1View(BasePositionView):
    """View class for v1/geolocate HTTP API."""

    metric_path = "v1.geolocate"
    route = "/v1/geolocate"
    schema = LOCATE_V1_SCHEMA

    def prepare_response(self, result):
        response = {
            "location": {"lat": result["lat"], "lng": result["lon"]},
            "accuracy": result["accuracy"],
        }

        if result["fallback"]:
            response["fallback"] = result["fallback"]

        return response


class RegionV1View(LocateV1View):
    """View class for v1/country HTTP API."""

    ip_log_and_rate_limit = False
    metric_path = "v1.country"
    renderer = "json"
    route = "/v1/country"
    searcher = "region_searcher"
    view_type = "region"

    def prepare_response(self, result):
        response = {
            "country_code": result["region_code"],
            "country_name": result["region_name"],
        }

        if result["fallback"]:
            response["fallback"] = result["fallback"]

        return response
