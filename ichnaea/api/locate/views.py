"""
Implementation of locate specific HTTP service views.
"""

import json

from structlog.threadlocal import bind_threadlocal

from ichnaea.api.exceptions import LocationNotFound
from ichnaea.api.locate.schema_v1 import LOCATE_V1_SCHEMA
from ichnaea.api.locate.query import Query
from ichnaea.api.views import BaseAPIView
from ichnaea.util import generate_signature, utcnow


class BaseLocateView(BaseAPIView):
    """Common base class for all locate related views."""

    not_found = LocationNotFound
    searcher = None

    def locate(self, api_key):
        request_data = self.preprocess_request()

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

        return self.prepare_response(result, api_key)


class BasePositionView(BaseLocateView):
    """Common base class for all position related views."""

    renderer = "json"
    searcher = "position_searcher"
    view_type = "locate"


class LocateV1View(BasePositionView):
    """View class for v1/geolocate HTTP API."""

    metric_path = "v1.geolocate"
    route = "/v1/geolocate"
    schema = LOCATE_V1_SCHEMA

    def prepare_response(self, result, api_key):
        response = {
            "location": {"lat": result["lat"], "lng": result["lon"]},
            "accuracy": result["accuracy"],
        }

        if result["fallback"]:
            response["fallback"] = result["fallback"]

        # Create a signature of the response, and look for unique responses
        response_content = json.dumps(response, sort_keys=True)
        response_sig = generate_signature(
            "response-sig",
            response_content,
            self.request.client_addr,
            self.request.url,  # Includes the API, API key
        )
        today = utcnow().date().isoformat()
        key = f"response-sig:{self.view_type}:{api_key.valid_key}:{today}"
        with self.redis_client.pipeline() as pipe:
            pipe.pfadd(key, response_sig)
            pipe.expire(key, 90000)  # 25 hours
            new_response, _ = pipe.execute()
        bind_threadlocal(
            api_repeat_response=not new_response, api_response_sig=response_sig[:8]
        )

        return response


class RegionV1View(LocateV1View):
    """View class for v1/country HTTP API."""

    ip_log_and_rate_limit = False
    metric_path = "v1.country"
    renderer = "json"
    route = "/v1/country"
    searcher = "region_searcher"
    view_type = "region"

    def prepare_response(self, result, api_key):
        response = {
            "country_code": result["region_code"],
            "country_name": result["region_name"],
        }

        if result["fallback"]:
            response["fallback"] = result["fallback"]

        return response
