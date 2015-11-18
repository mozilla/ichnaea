"""
Implementation of a locate specific HTTP service view.
"""

from ichnaea.api.exceptions import LocationNotFound
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
