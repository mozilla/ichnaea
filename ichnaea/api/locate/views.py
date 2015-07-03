from ichnaea.api.exceptions import LocationNotFound
from ichnaea.api.locate.searcher import PositionSearcher
from ichnaea.api.views import BaseAPIView


class BaseLocateView(BaseAPIView):

    not_found = LocationNotFound
    searcher = PositionSearcher
    schema = None

    def prepare_query(self, request_data):
        return {
            'geoip': self.request.client_addr,
            'cell': request_data.get('cell', []),
            'wifi': request_data.get('wifi', []),
            'fallbacks': request_data.get('fallbacks', {}),
        }

    def locate(self, api_key):
        request_data, errors = self.preprocess_request()
        query = self.prepare_query(request_data)

        return self.searcher(
            session_db=self.request.db_ro_session,
            geoip_db=self.request.registry.geoip_db,
            redis_client=self.request.registry.redis_client,
            settings=self.request.registry.settings,
            api_key=api_key,
            api_name=self.view_name,
        ).search(query)

    def prepare_location_data(self, location_data):  # pragma: no cover
        return location_data

    def view(self, api_key):
        location_data = self.locate(api_key)
        if not location_data:
            raise self.not_found()

        return self.prepare_location_data(location_data)
