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
    schema = None  #:

    def locate(self, api_key):
        request_data, errors = self.preprocess_request()

        query = Query(
            fallback=request_data.get('fallbacks'),
            geoip=self.request.client_addr,
            cell=request_data.get('cell'),
            wifi=request_data.get('wifi'),
            api_key=api_key,
            api_name=self.view_name,
            session=self.request.db_ro_session,
            stats_client=self.stats_client,
        )

        searcher = getattr(self.request.registry, self.searcher)
        return searcher.search(query)

    def prepare_location_data(self, location_data):  # pragma: no cover
        return location_data

    def view(self, api_key):
        """
        Execute the view code and return a response.
        """
        location_data = self.locate(api_key)
        if not location_data:
            raise self.not_found()

        return self.prepare_location_data(location_data)


class BasePositionView(BaseLocateView):
    """Common base class for all position related views."""

    #: Use renderer with prettier float output.
    renderer = 'floatjson'
    searcher = 'position_searcher'
