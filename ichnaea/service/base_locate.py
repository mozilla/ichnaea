from pyramid.httpexceptions import HTTPNotFound
from simplejson import dumps

from ichnaea.locate.searcher import PositionSearcher
from ichnaea.models.transform import ReportTransform
from ichnaea.service.base import BaseAPIView
from ichnaea.service.error import (
    JSONParseError,
    preprocess_request,
)
from ichnaea.service.geolocate.schema import GeoLocateSchema

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


class LocateTransform(ReportTransform):

    radio_id = ('radioType', 'radio')
    cell_id = ('cellTowers', 'cell')
    cell_map = [
        # if both radio and radioType are present in the source,
        # radioType takes precedence
        ('radio', 'radio'),
        ('radioType', 'radio'),
        ('mobileCountryCode', 'mcc'),
        ('mobileNetworkCode', 'mnc'),
        ('locationAreaCode', 'lac'),
        ('cellId', 'cid'),
        'psc',
        ('signalStrength', 'signal'),
        ('timingAdvance', 'ta'),
    ]

    wifi_id = ('wifiAccessPoints', 'wifi')
    wifi_map = [
        ('macAddress', 'key'),
        'channel',
        'frequency',
        ('signalToNoiseRatio', 'snr'),
        ('signalStrength', 'signal'),
    ]


class BaseLocateView(BaseAPIView):

    error_response = JSONParseError
    searcher = PositionSearcher
    transform = LocateTransform
    schema = GeoLocateSchema

    def not_found(self):
        result = HTTPNotFound()
        result.content_type = 'application/json'
        result.body = NOT_FOUND
        return result

    def prepare_query(self, request_data):
        transform = self.transform()
        parsed_data = transform.transform_one(request_data)

        query = {
            'geoip': self.request.client_addr,
            'cell': parsed_data.get('cell', []),
            'wifi': parsed_data.get('wifi', []),
            'fallbacks': request_data.get('fallbacks', {}),
        }
        return query

    def locate(self, api_key):
        request_data, errors = preprocess_request(
            self.request,
            schema=self.schema(),
            response=self.error_response,
            accept_empty=True,
        )
        query = self.prepare_query(request_data)

        return self.searcher(
            session_db=self.request.db_ro_session,
            geoip_db=self.request.registry.geoip_db,
            redis_client=self.request.registry.redis_client,
            settings=self.request.registry.settings,
            api_key=api_key,
            api_name=self.view_name,
        ).search(query)
