from pyramid.httpexceptions import (
    HTTPOk,
    HTTPServiceUnavailable,
)
from redis import ConnectionError

from ichnaea.models.transform import ReportTransform
from ichnaea.service.base import check_api_key
from ichnaea.service.base_submit import BaseSubmitter
from ichnaea.service.error import JSONParseError
from ichnaea.service.geosubmit.schema import GeoSubmitBatchSchema


def configure_geosubmit(config):
    config.add_route('v1_geosubmit', '/v1/geosubmit')
    config.add_view(geosubmit_view, route_name='v1_geosubmit', renderer='json')


class GeoSubmitTransform(ReportTransform):

    toplevel_map = [
        ('carrier', 'carrier', None),
        ('homeMobileCountryCode', 'homeMobileCountryCode', None),
        ('homeMobileNetworkCode', 'homeMobileNetworkCode', None),
    ]

    position_id = (None, 'position')
    position_map = [
        ('latitude', 'latitude', None),
        ('longitude', 'longitude', None),
        ('accuracy', 'accuracy', None),
        ('altitude', 'altitude', None),
        ('altitudeAccuracy', 'altitudeAccuracy', None),
        ('age', 'age', None),
        ('heading', 'heading', None),
        ('pressure', 'pressure', None),
        ('speed', 'speed', None),
        ('source', 'source', None),
    ]

    radio_id = ('radioType', 'radioType')
    cell_id = ('cellTowers', 'cellTowers')
    cell_map = [
        ('radioType', 'radioType', None),
        ('mobileCountryCode', 'mobileCountryCode', None),
        ('mobileNetworkCode', 'mobileNetworkCode', None),
        ('locationAreaCode', 'locationAreaCode', None),
        ('cellId', 'cellId', None),
        ('age', 'age', None),
        ('asu', 'asu', None),
        ('psc', 'primaryScramblingCode', None),
        ('serving', 'serving', None),
        ('signalStrength', 'signalStrength', None),
        ('timingAdvance', 'timingAdvance', None),
    ]

    wifi_id = ('wifiAccessPoints', 'wifiAccessPoints')
    wifi_map = [
        ('macAddress', 'macAddress', None),
        ('age', 'age', None),
        ('channel', 'channel', None),
        ('frequency', 'frequency', None),
        ('radioType', 'radioType', None),
        ('signalToNoiseRatio', 'signalToNoiseRatio', None),
        ('signalStrength', 'signalStrength', None),
        # ssid is not mapped on purpose, we never want to store it
    ]

    def _parse_extra(self, item, report):
        self._parse_timestamp(item, report)


class GeoSubmitter(BaseSubmitter):

    schema = GeoSubmitBatchSchema
    error_response = JSONParseError

    def prepare_reports(self, request_data):
        transform = GeoSubmitTransform()
        return transform.transform_many(request_data['items'])


@check_api_key('geosubmit', error_on_invalidkey=False)
def geosubmit_view(request, api_key):
    submitter = GeoSubmitter(request, api_key)

    # may raise HTTP error
    request_data = submitter.preprocess()

    try:
        submitter.submit(request_data)
    except ConnectionError:  # pragma: no cover
        return HTTPServiceUnavailable()

    result = HTTPOk()
    result.content_type = 'application/json'
    result.body = '{}'
    return result
