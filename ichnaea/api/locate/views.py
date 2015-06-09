from pyramid.httpexceptions import HTTPNotFound
from simplejson import dumps

from ichnaea.api.locate.searcher import PositionSearcher
from ichnaea.api.error import (
    JSONParseError,
)
from ichnaea.api.views import BaseAPIView

NOT_FOUND = {
    'error': {
        'errors': [{
            'domain': 'geolocation',
            'reason': 'notFound',
            'message': 'Not found',
        }],
        'code': 404,
        'message': 'Not found',
    }
}
NOT_FOUND = dumps(NOT_FOUND)


class BaseLocateView(BaseAPIView):

    error_response = JSONParseError
    searcher = PositionSearcher
    schema = None

    def not_found(self):
        result = HTTPNotFound()
        result.content_type = 'application/json'
        result.body = NOT_FOUND
        return result

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
            return self.not_found()

        return self.prepare_location_data(location_data)
